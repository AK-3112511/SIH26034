import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';
import '../../features/scans/models/capture_record.dart';

/// Database Helper for Local SQLite captures table
/// Source: MetrologyAI_Elevated_Blueprint.md §3.1
class DatabaseHelper {
  static final DatabaseHelper _instance = DatabaseHelper._internal();
  factory DatabaseHelper() => _instance;
  DatabaseHelper._internal();

  Database? _db;

  @visibleForTesting
  void setDatabase(Database db) {
    _db = db;
  }

  Future<Database> get database async {
    if (_db != null) return _db!;
    _db = await _initDatabase();
    return _db!;
  }

  Future<Database> _initDatabase() async {
    final docsDir = await getApplicationDocumentsDirectory();
    final dbPath = p.join(docsDir.path, 'metrologyai_local.db');

    return await openDatabase(
      dbPath,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE captures (
            local_id TEXT PRIMARY KEY,
            image_path TEXT,
            lat REAL,
            lng REAL,
            captured_at_utc TEXT,
            reference_object_type TEXT,
            sync_status TEXT,
            retry_count INTEGER DEFAULT 0,
            server_scan_id TEXT
          )
        ''');
      },
    );
  }

  /// Insert a new local capture record
  Future<void> insertCapture(CaptureRecord capture) async {
    final db = await database;
    await db.insert(
      'captures',
      capture.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Query batch of captures ready for sync (§3.1 pseudo-code: sync_status in ('PENDING_UPLOAD', 'FAILED') limit 10)
  Future<List<CaptureRecord>> getPendingOrFailedCaptures({int limit = 10}) async {
    final db = await database;
    final results = await db.query(
      'captures',
      where: "sync_status IN ('PENDING_UPLOAD', 'FAILED') AND retry_count <= 10",
      orderBy: 'captured_at_utc ASC',
      limit: limit,
    );

    return results.map((map) => CaptureRecord.fromMap(map)).toList();
  }

  /// Update sync status and retry count
  Future<void> updateSyncStatus(
    String localId,
    String status, {
    String? serverScanId,
    int? retryCount,
  }) async {
    final db = await database;
    final values = <String, dynamic>{
      'sync_status': status,
    };
    if (serverScanId != null) {
      values['server_scan_id'] = serverScanId;
    }
    if (retryCount != null) {
      values['retry_count'] = retryCount;
    }

    await db.update(
      'captures',
      values,
      where: 'local_id = ?',
      whereArgs: [localId],
    );
  }

  /// Mark capture as SYNCED and delete local image file (§3.1 requirement)
  Future<void> markSyncedAndCleanLocalImage({
    required String localId,
    required String? imagePath,
    required String serverScanId,
  }) async {
    // 1. Physically delete local image file from device storage
    if (imagePath != null && imagePath.isNotEmpty) {
      try {
        final file = File(imagePath);
        if (file.existsSync()) {
          file.deleteSync();
        }
      } catch (e) {
        debugPrint('Error deleting local synced image file: $e');
      }
    }

    // 2. Update record in SQLite: sync_status = 'SYNCED', server_scan_id = serverScanId, image_path = NULL
    final db = await database;
    await db.update(
      'captures',
      {
        'sync_status': 'SYNCED',
        'server_scan_id': serverScanId,
        'image_path': null,
      },
      where: 'local_id = ?',
      whereArgs: [localId],
    );
  }

  /// Retrieve all captures recorded on device (for Home screen display)
  Future<List<CaptureRecord>> getAllCaptures() async {
    final db = await database;
    final results = await db.query(
      'captures',
      orderBy: 'captured_at_utc DESC',
    );

    return results.map((map) => CaptureRecord.fromMap(map)).toList();
  }

  /// Retrieve all pending, failed, and stuck captures for the Sync Queue Screen (§2 Screen 6)
  Future<List<CaptureRecord>> getUnsyncedCaptures() async {
    final db = await database;
    final results = await db.query(
      'captures',
      where: "sync_status != 'SYNCED'",
      orderBy: 'captured_at_utc DESC',
    );

    return results.map((map) => CaptureRecord.fromMap(map)).toList();
  }

  /// Reset retry count for a stuck capture and set to PENDING_UPLOAD for manual retry
  Future<void> resetCaptureRetry(String localId) async {
    final db = await database;
    await db.update(
      'captures',
      {
        'retry_count': 0,
        'sync_status': 'PENDING_UPLOAD',
      },
      where: 'local_id = ?',
      whereArgs: [localId],
    );
  }

  /// Delete a capture record and clean up its local file
  Future<void> deleteCapture(String localId, String? imagePath) async {
    if (imagePath != null && imagePath.isNotEmpty) {
      try {
        final file = File(imagePath);
        if (file.existsSync()) {
          file.deleteSync();
        }
      } catch (e) {
        debugPrint('Error deleting local image file on discard: $e');
      }
    }

    final db = await database;
    await db.delete(
      'captures',
      where: 'local_id = ?',
      whereArgs: [localId],
    );
  }

  /// Clear all captures (for testing and reset)
  Future<void> clearAll() async {
    final db = await database;
    await db.delete('captures');
  }
}
