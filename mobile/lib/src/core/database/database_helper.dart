import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';
import '../../features/scans/models/capture_record.dart';
import '../../features/scans/models/assigned_task_record.dart';
import '../../features/notifications/models/notification_item.dart';

/// Database Helper for the on-device SQLite store.
///
/// Holds three tables:
///  * `captures` - the offline capture queue and the verdict the server
///    later returns for each one;
///  * `assigned_tasks` - follow-up work pushed down from the dashboard;
///  * `notifications` - the in-app feed, so alerts survive an app restart.
class DatabaseHelper {
  static final DatabaseHelper _instance = DatabaseHelper._internal();
  factory DatabaseHelper() => _instance;
  DatabaseHelper._internal();

  /// Bumped whenever the schema below changes. `onUpgrade` must be able to
  /// bring any older installation forward without losing queued evidence.
  static const int schemaVersion = 2;

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
      version: schemaVersion,
      onCreate: (db, version) async {
        await createSchema(db);
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        await migrate(db, oldVersion, newVersion);
      },
    );
  }

  /// Full schema for a fresh install. Kept public so tests can build an
  /// in-memory database that matches production exactly.
  static Future<void> createSchema(Database db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS captures (
        local_id TEXT PRIMARY KEY,
        image_path TEXT,
        lat REAL,
        lng REAL,
        accuracy_m REAL,
        captured_at_utc TEXT,
        reference_object_type TEXT,
        product_type TEXT,
        product_name TEXT,
        device_id TEXT,
        sync_status TEXT,
        retry_count INTEGER DEFAULT 0,
        next_attempt_at_utc TEXT,
        last_error TEXT,
        server_scan_id TEXT,
        server_status TEXT,
        verdict_summary TEXT,
        rule_failures TEXT
      )
    ''');
    await db.execute('''
      CREATE TABLE IF NOT EXISTS assigned_tasks (
        scan_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        platform TEXT,
        location TEXT,
        assigned_at_utc TEXT,
        task_type TEXT,
        status TEXT,
        instructions TEXT
      )
    ''');
    await db.execute('''
      CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        category TEXT NOT NULL,
        timestamp_utc TEXT NOT NULL,
        is_read INTEGER NOT NULL DEFAULT 0,
        deep_link_route TEXT
      )
    ''');
  }

  /// Additive migration: every statement adds something, so a device holding
  /// unsynced captures upgrades without dropping evidence.
  static Future<void> migrate(Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 2) {
      const newCaptureColumns = <String, String>{
        'accuracy_m': 'REAL',
        'product_type': 'TEXT',
        'product_name': 'TEXT',
        'device_id': 'TEXT',
        'next_attempt_at_utc': 'TEXT',
        'last_error': 'TEXT',
        'server_status': 'TEXT',
        'verdict_summary': 'TEXT',
        'rule_failures': 'TEXT',
      };
      for (final entry in newCaptureColumns.entries) {
        try {
          await db.execute('ALTER TABLE captures ADD COLUMN ${entry.key} ${entry.value}');
        } catch (e) {
          // Column already present (partial upgrade, or created by createSchema).
          debugPrint('[DatabaseHelper] Skipping captures.${entry.key}: $e');
        }
      }
      await db.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          category TEXT NOT NULL,
          timestamp_utc TEXT NOT NULL,
          is_read INTEGER NOT NULL DEFAULT 0,
          deep_link_route TEXT
        )
      ''');
      await db.execute('''
        CREATE TABLE IF NOT EXISTS assigned_tasks (
          scan_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          platform TEXT,
          location TEXT,
          assigned_at_utc TEXT,
          task_type TEXT,
          status TEXT,
          instructions TEXT
        )
      ''');
    }
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

  /// Batch of captures ready for upload.
  ///
  /// Honours the backoff clock: a record that failed recently is skipped until
  /// `next_attempt_at_utc` has passed, so a flapping network does not burn
  /// through the retry budget in seconds.
  Future<List<CaptureRecord>> getPendingOrFailedCaptures({int limit = 10}) async {
    final db = await database;
    final nowUtc = DateTime.now().toUtc().toIso8601String();
    final results = await db.query(
      'captures',
      where: "sync_status IN ('PENDING_UPLOAD', 'FAILED') AND retry_count <= 10 "
          "AND (next_attempt_at_utc IS NULL OR next_attempt_at_utc <= ?)",
      whereArgs: [nowUtc],
      orderBy: 'captured_at_utc ASC',
      limit: limit,
    );

    return results.map((map) => CaptureRecord.fromMap(map)).toList();
  }

  /// Captures the server has accepted but not yet reached a verdict on.
  /// These are what the verdict poller asks about.
  Future<List<CaptureRecord>> getCapturesAwaitingVerdict() async {
    final db = await database;
    final results = await db.query(
      'captures',
      where: "server_scan_id IS NOT NULL AND server_scan_id != '' "
          "AND (server_status IS NULL OR server_status IN ('QUEUED', 'PROCESSING'))",
      orderBy: 'captured_at_utc DESC',
    );
    return results.map((map) => CaptureRecord.fromMap(map)).toList();
  }

  /// Re-queue rows left in UPLOADING by a crash or a force-stop mid-upload.
  /// Without this they are invisible to both the upload query and the user.
  Future<int> recoverOrphanedUploads() async {
    final db = await database;
    return db.update(
      'captures',
      {'sync_status': 'PENDING_UPLOAD', 'next_attempt_at_utc': null},
      where: "sync_status = 'UPLOADING'",
    );
  }

  /// Update sync status, retry count, backoff deadline and last error.
  Future<void> updateSyncStatus(
    String localId,
    String status, {
    String? serverScanId,
    int? retryCount,
    String? lastError,
    DateTime? nextAttemptAt,
    bool clearBackoff = false,
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
    if (lastError != null) {
      values['last_error'] = lastError;
    }
    if (clearBackoff) {
      values['next_attempt_at_utc'] = null;
    } else if (nextAttemptAt != null) {
      values['next_attempt_at_utc'] = nextAttemptAt.toUtc().toIso8601String();
    }

    await db.update(
      'captures',
      values,
      where: 'local_id = ?',
      whereArgs: [localId],
    );
  }

  /// Mark capture as SYNCED and delete the local image file: once the server
  /// holds the evidence, keeping a second copy only fills the handset.
  Future<void> markSyncedAndCleanLocalImage({
    required String localId,
    required String? imagePath,
    required String serverScanId,
  }) async {
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

    final db = await database;
    await db.update(
      'captures',
      {
        'sync_status': 'SYNCED',
        'server_scan_id': serverScanId,
        'image_path': null,
        'last_error': null,
        'next_attempt_at_utc': null,
      },
      where: 'local_id = ?',
      whereArgs: [localId],
    );
  }

  /// Record the verdict the backend reached for an already-synced capture.
  Future<void> updateServerVerdict({
    required String localId,
    required String serverStatus,
    String? verdictSummary,
    String? ruleFailuresJson,
  }) async {
    final db = await database;
    await db.update(
      'captures',
      {
        'server_status': serverStatus,
        'verdict_summary': verdictSummary,
        'rule_failures': ruleFailuresJson,
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

  Future<CaptureRecord?> getCaptureById(String localId) async {
    final db = await database;
    final results = await db.query(
      'captures',
      where: 'local_id = ?',
      whereArgs: [localId],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return CaptureRecord.fromMap(results.first);
  }

  /// Find the local row for a scan the server knows about. Used to resolve a
  /// notification deep link (which carries the server id) back to the capture
  /// this device holds.
  Future<CaptureRecord?> getCaptureByServerScanId(String serverScanId) async {
    final db = await database;
    final results = await db.query(
      'captures',
      where: 'server_scan_id = ?',
      whereArgs: [serverScanId],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return CaptureRecord.fromMap(results.first);
  }

  /// Retrieve all pending, failed, and stuck captures for the Sync Queue Screen
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
        'next_attempt_at_utc': null,
        'last_error': null,
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

  // --- Assigned tasks -------------------------------------------------------

  /// Insert or update an assigned task record in SQLite
  Future<void> insertAssignedTask(AssignedTaskRecord task) async {
    final db = await database;
    await db.insert(
      'assigned_tasks',
      task.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Batch insert assigned tasks from remote sync
  Future<void> insertAssignedTasks(List<AssignedTaskRecord> tasks) async {
    final db = await database;
    final batch = db.batch();
    for (final task in tasks) {
      batch.insert(
        'assigned_tasks',
        task.toMap(),
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  /// Get all assigned tasks ordered by assignment time
  Future<List<AssignedTaskRecord>> getAllAssignedTasks() async {
    final db = await database;
    final results = await db.query(
      'assigned_tasks',
      orderBy: 'assigned_at_utc DESC',
    );
    return results.map((m) => AssignedTaskRecord.fromMap(m)).toList();
  }

  /// Delete an assigned task by scan_id
  Future<void> deleteAssignedTask(String scanId) async {
    final db = await database;
    await db.delete(
      'assigned_tasks',
      where: 'scan_id = ?',
      whereArgs: [scanId],
    );
  }

  /// Clear all assigned tasks (for testing/logout)
  Future<void> clearAssignedTasks() async {
    final db = await database;
    await db.delete('assigned_tasks');
  }

  // --- Notifications --------------------------------------------------------

  /// Persist a notification. Replaces on conflict so the headless WorkManager
  /// isolate and the foreground poller cannot double-insert the same alert.
  Future<void> insertNotification(NotificationItem item) async {
    final db = await database;
    await db.insert(
      'notifications',
      item.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<NotificationItem>> getNotifications({int limit = 100}) async {
    final db = await database;
    final results = await db.query(
      'notifications',
      orderBy: 'timestamp_utc DESC',
      limit: limit,
    );
    return results.map((m) => NotificationItem.fromMap(m)).toList();
  }

  Future<void> markNotificationRead(String id) async {
    final db = await database;
    await db.update(
      'notifications',
      {'is_read': 1},
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  Future<void> markAllNotificationsRead() async {
    final db = await database;
    await db.update('notifications', {'is_read': 1});
  }

  Future<void> clearNotifications() async {
    final db = await database;
    await db.delete('notifications');
  }
}
