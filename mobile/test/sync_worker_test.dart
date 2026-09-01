import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:mobile/src/core/database/database_helper.dart';
import 'package:mobile/src/features/scans/models/capture_record.dart';
import 'package:mobile/src/features/scans/services/sync_worker.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();

  late Database db;
  late DatabaseHelper dbHelper;

  setUp(() async {
    final databaseFactory = databaseFactoryFfi;
    db = await databaseFactory.openDatabase(inMemoryDatabasePath);
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

    dbHelper = DatabaseHelper();
    dbHelper.setDatabase(db);
  });

  tearDown(() async {
    await db.close();
  });

  group('SQLite DatabaseHelper (§3.1 Schema & Local Queue)', () {
    test('inserts capture and retrieves pending/failed items', () async {
      final record = CaptureRecord(
        localId: 'loc-001',
        imagePath: '/tmp/test_image.jpg',
        lat: 11.0168,
        lng: 76.9558,
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'debit_card',
        syncStatus: 'PENDING_UPLOAD',
        retryCount: 0,
      );

      await dbHelper.insertCapture(record);

      final pending = await dbHelper.getPendingOrFailedCaptures(limit: 10);
      expect(pending.length, equals(1));
      expect(pending.first.localId, equals('loc-001'));
      expect(pending.first.syncStatus, equals('PENDING_UPLOAD'));
    });

    test('markSyncedAndCleanLocalImage deletes physical file and updates record to SYNCED', () async {
      // Create a temporary physical test file on disk
      final tempDir = Directory.systemTemp.createTempSync('metrology_test_');
      final tempFile = File('${tempDir.path}/capture_loc_002.jpg');
      await tempFile.writeAsBytes([0xFF, 0xD8, 0xFF, 0xE0]);
      expect(await tempFile.exists(), isTrue);

      final record = CaptureRecord(
        localId: 'loc-002',
        imagePath: tempFile.path,
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'bottle',
        syncStatus: 'UPLOADING',
        retryCount: 0,
      );
      await dbHelper.insertCapture(record);

      // Perform sync completion and local file cleanup (§3.1)
      await dbHelper.markSyncedAndCleanLocalImage(
        localId: 'loc-002',
        imagePath: tempFile.path,
        serverScanId: 'srv-scan-uuid-777',
      );

      // Verify physical file was deleted
      expect(await tempFile.exists(), isFalse);

      // Verify SQLite record updated
      final all = await dbHelper.getAllCaptures();
      expect(all.length, equals(1));
      expect(all.first.syncStatus, equals('SYNCED'));
      expect(all.first.serverScanId, equals('srv-scan-uuid-777'));
      expect(all.first.imagePath, isNull);

      tempDir.deleteSync(recursive: true);
    });
  });

  group('SyncWorker (§3.1 Pseudo-Code & Airplane Mode Invariance)', () {
    test('Simulated Airplane Mode: capture succeeds locally, sync marks FAILED and increments retry_count', () async {
      final record = CaptureRecord(
        localId: 'loc-offline-01',
        imagePath: '/fake/path/img.jpg',
        lat: 13.0827,
        lng: 80.2707,
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'box',
        syncStatus: 'PENDING_UPLOAD',
        retryCount: 0,
      );
      await dbHelper.insertCapture(record);

      // Mock offline client that throws SocketException (Airplane mode / no server)
      final offlineClient = MockClient((request) async {
        throw const SocketException('No route to host (Airplane mode active)');
      });

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(dbHelper: dbHelper, client: offlineClient);

      final syncedCount = await syncWorker.syncPendingCaptures();
      expect(syncedCount, equals(0));

      final captures = await dbHelper.getAllCaptures();
      expect(captures.first.syncStatus, equals('FAILED'));
      expect(captures.first.retryCount, equals(1));
    });

    test('Network Restored: pending/failed captures sync to /scans/ingest and delete local file', () async {
      // Create temporary local file
      final tempDir = Directory.systemTemp.createTempSync('metrology_sync_');
      final tempFile = File('${tempDir.path}/capture_sync_01.jpg');
      await tempFile.writeAsBytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10]);

      final failedRecord = CaptureRecord(
        localId: 'loc-retry-01',
        imagePath: tempFile.path,
        lat: 11.0168,
        lng: 76.9558,
        capturedAtUtc: '2026-09-01T12:00:00.000Z',
        referenceObjectType: 'debit_card',
        syncStatus: 'FAILED',
        retryCount: 1,
      );
      await dbHelper.insertCapture(failedRecord);

      // Mock successful backend response (HTTP 201 Created from /api/v1/scans/ingest)
      final onlineClient = MockClient((request) async {
        expect(request.url.path, contains('/scans/ingest'));
        return http.Response(
          jsonEncode({
            'scan_id': '4c8e7456-9b1b-4f8a-a123-abcdef123456',
            'status': 'QUEUED',
            'image_url': 'http://storage.metrologyai.gov.in/scans/scan_01.jpg',
            'evidence_hash': 'sha256:abc123def456',
            'captured_at_utc': '2026-09-01T12:00:00.000Z',
            'created_at': '2026-09-01T12:01:00.000Z',
            'message': 'Scan received and queued for processing'
          }),
          201,
          headers: {'content-type': 'application/json'},
        );
      });

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(dbHelper: dbHelper, client: onlineClient);

      final syncedCount = await syncWorker.syncPendingCaptures();
      expect(syncedCount, equals(1));

      // Verify local file was deleted upon successful sync
      expect(await tempFile.exists(), isFalse);

      // Verify SQLite state updated to SYNCED with server scan ID
      final all = await dbHelper.getAllCaptures();
      expect(all.first.syncStatus, equals('SYNCED'));
      expect(all.first.serverScanId, equals('4c8e7456-9b1b-4f8a-a123-abcdef123456'));

      tempDir.deleteSync(recursive: true);
    });

    test('Exceeding max retries (> 10) flags photo as stuck (§3.1)', () async {
      final stuckRecord = CaptureRecord(
        localId: 'loc-stuck-99',
        imagePath: '/dummy/stuck.jpg',
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'pan_card',
        syncStatus: 'FAILED',
        retryCount: 10,
      );
      await dbHelper.insertCapture(stuckRecord);

      final failingClient = MockClient((request) async {
        throw const SocketException('Continuous network outage');
      });

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(dbHelper: dbHelper, client: failingClient);

      await syncWorker.syncPendingCaptures();

      final updated = await dbHelper.getAllCaptures();
      expect(updated.first.retryCount, equals(11));
      expect(syncWorker.stuckPhotos, contains('loc-stuck-99'));
    });
  });
}
