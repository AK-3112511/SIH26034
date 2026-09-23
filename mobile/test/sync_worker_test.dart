import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:mobile/src/core/database/database_helper.dart';
import 'package:mobile/src/features/auth/data/auth_service.dart';
import 'package:mobile/src/features/scans/models/capture_record.dart';
import 'package:mobile/src/features/scans/services/sync_worker.dart';

/// Bytes large enough to pass the worker's evidence check, which rejects
/// anything too small to be an actual photograph.
List<int> realisticJpegBytes() => <int>[
      0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46,
      ...List.filled(4096, 0x7F),
    ];

/// An AuthService holding a token the server issued, which every upload needs.
Future<AuthService> signedInAuth() async {
  final auth = AuthService.createTestInstance(
    client: MockClient((request) async => http.Response(
          jsonEncode({
            'access_token': 'test-jwt-token',
            'token_type': 'bearer',
            'user': {
              'id': 'officer-1',
              'username': 'lmo_test',
              'email': 'lmo_test@legalmetrology.gov.in',
              'full_name': 'Test Officer',
              'role': 'field_lmo',
              'district': 'Chennai, TN',
              'is_active': true,
            },
          }),
          200,
          headers: {'content-type': 'application/json'},
        )),
  );
  await auth.login(username: 'lmo_test', password: 'secret');
  return auth;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  sqfliteFfiInit();

  late Database db;
  late DatabaseHelper dbHelper;

  setUp(() async {
    final databaseFactory = databaseFactoryFfi;
    db = await databaseFactory.openDatabase(inMemoryDatabasePath);
    // Use the app's own schema rather than a copy, so a migration that misses
    // a column fails here instead of on a field officer's handset.
    await DatabaseHelper.createSchema(db);

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
      await tempFile.writeAsBytes(realisticJpegBytes());
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
      final tempDir = Directory.systemTemp.createTempSync('metrology_offline_');
      final tempFile = File('${tempDir.path}/capture_offline_01.jpg');
      await tempFile.writeAsBytes(realisticJpegBytes());

      final record = CaptureRecord(
        localId: 'loc-offline-01',
        imagePath: tempFile.path,
        lat: 13.0827,
        lng: 80.2707,
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'debit_card',
        productType: 'box',
        syncStatus: 'PENDING_UPLOAD',
        retryCount: 0,
      );
      await dbHelper.insertCapture(record);

      // Mock offline client that throws SocketException (Airplane mode / no server)
      final offlineClient = MockClient((request) async {
        throw const SocketException('No route to host (Airplane mode active)');
      });

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(
        dbHelper: dbHelper,
        client: offlineClient,
        authService: await signedInAuth(),
      );

      final syncedCount = await syncWorker.syncPendingCaptures();
      expect(syncedCount, equals(0));

      final captures = await dbHelper.getAllCaptures();
      expect(captures.first.syncStatus, equals('FAILED'));
      expect(captures.first.retryCount, equals(1));
      // The photo is untouched on disk: a failed attempt loses no evidence.
      expect(await tempFile.exists(), isTrue);
      // A backoff deadline is set so a flapping network cannot burn the budget.
      expect(captures.first.nextAttemptAtUtc, isNotNull);

      tempDir.deleteSync(recursive: true);
    });

    test('an unauthenticated run leaves the queue untouched', () async {
      final tempDir = Directory.systemTemp.createTempSync('metrology_noauth_');
      final tempFile = File('${tempDir.path}/capture_noauth.jpg');
      await tempFile.writeAsBytes(realisticJpegBytes());

      await dbHelper.insertCapture(CaptureRecord(
        localId: 'loc-noauth-01',
        imagePath: tempFile.path,
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'debit_card',
        syncStatus: 'PENDING_UPLOAD',
      ));

      var requestWasMade = false;
      final client = MockClient((request) async {
        requestWasMade = true;
        return http.Response('{}', 201);
      });

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(
        dbHelper: dbHelper,
        client: client,
        // No session: the backend attributes a scan to the officer who took it,
        // so an anonymous upload has no evidentiary value.
        authService: AuthService.createTestInstance(),
      );

      expect(await syncWorker.syncPendingCaptures(), equals(0));
      expect(requestWasMade, isFalse);
      expect(syncWorker.lastSyncError, contains('Sign in'));

      final captures = await dbHelper.getAllCaptures();
      expect(captures.first.syncStatus, equals('PENDING_UPLOAD'));
      expect(captures.first.retryCount, equals(0));

      tempDir.deleteSync(recursive: true);
    });

    test('a capture whose photo is gone is parked, never uploaded as a placeholder', () async {
      await dbHelper.insertCapture(CaptureRecord(
        localId: 'loc-missing-01',
        imagePath: '/no/such/file.jpg',
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'debit_card',
        syncStatus: 'PENDING_UPLOAD',
      ));

      var requestWasMade = false;
      final client = MockClient((request) async {
        requestWasMade = true;
        return http.Response('{}', 201);
      });

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(
        dbHelper: dbHelper,
        client: client,
        authService: await signedInAuth(),
      );

      expect(await syncWorker.syncPendingCaptures(), equals(0));
      // Uploading synthetic bytes would attach an evidence hash to a photo that
      // was never taken.
      expect(requestWasMade, isFalse);

      final captures = await dbHelper.getAllCaptures();
      expect(captures.first.syncStatus, equals('FAILED'));
      expect(captures.first.retryCount, greaterThan(kMaxSyncRetries));
      expect(captures.first.lastError, contains('missing from device storage'));
    });

    test('a 401 mid-shift stops the run and ends the session', () async {
      final tempDir = Directory.systemTemp.createTempSync('metrology_401_');
      final tempFile = File('${tempDir.path}/capture_401.jpg');
      await tempFile.writeAsBytes(realisticJpegBytes());

      await dbHelper.insertCapture(CaptureRecord(
        localId: 'loc-401-01',
        imagePath: tempFile.path,
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'debit_card',
        syncStatus: 'PENDING_UPLOAD',
      ));

      final auth = await signedInAuth();
      final syncWorker = SyncWorker();
      syncWorker.setDependencies(
        dbHelper: dbHelper,
        client: MockClient((request) async => http.Response('{"detail":"expired"}', 401)),
        authService: auth,
      );

      expect(await syncWorker.syncPendingCaptures(), equals(0));
      expect(auth.isAuthenticated, isFalse);
      expect(auth.sessionEndedReason, isNotNull);

      // The capture goes back to PENDING_UPLOAD rather than burning a retry on
      // a request that could never have succeeded.
      final captures = await dbHelper.getAllCaptures();
      expect(captures.first.syncStatus, equals('PENDING_UPLOAD'));
      expect(captures.first.retryCount, equals(0));

      tempDir.deleteSync(recursive: true);
    });

    test('recovers captures orphaned mid-upload by a crash', () async {
      await dbHelper.insertCapture(CaptureRecord(
        localId: 'loc-orphan-01',
        imagePath: '/some/path.jpg',
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'debit_card',
        syncStatus: 'UPLOADING',
      ));

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(dbHelper: dbHelper);

      expect(await syncWorker.recoverOrphanedUploads(), equals(1));
      final captures = await dbHelper.getAllCaptures();
      expect(captures.first.syncStatus, equals('PENDING_UPLOAD'));
    });

    test('backoff grows with each retry and is capped', () {
      expect(SyncWorker.backoffDelay(1), const Duration(seconds: 30));
      expect(SyncWorker.backoffDelay(2), const Duration(seconds: 60));
      expect(SyncWorker.backoffDelay(3), const Duration(seconds: 120));
      expect(SyncWorker.backoffDelay(20), const Duration(minutes: 30));
    });

    test('Network Restored: pending/failed captures sync to /scans/ingest and delete local file', () async {
      // Create temporary local file
      final tempDir = Directory.systemTemp.createTempSync('metrology_sync_');
      final tempFile = File('${tempDir.path}/capture_sync_01.jpg');
      await tempFile.writeAsBytes(realisticJpegBytes());

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
      syncWorker.setDependencies(
        dbHelper: dbHelper,
        client: onlineClient,
        authService: await signedInAuth(),
      );

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
      final tempDir = Directory.systemTemp.createTempSync('metrology_stuck_');
      final tempFile = File('${tempDir.path}/capture_stuck.jpg');
      await tempFile.writeAsBytes(realisticJpegBytes());

      final stuckRecord = CaptureRecord(
        localId: 'loc-stuck-99',
        imagePath: tempFile.path,
        capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
        referenceObjectType: 'pan_card',
        syncStatus: 'FAILED',
        retryCount: 10,
      );
      await dbHelper.insertCapture(stuckRecord);
      addTearDown(() => tempDir.deleteSync(recursive: true));

      final failingClient = MockClient((request) async {
        throw const SocketException('Continuous network outage');
      });

      final syncWorker = SyncWorker();
      syncWorker.setDependencies(
        dbHelper: dbHelper,
        client: failingClient,
        authService: await signedInAuth(),
      );

      await syncWorker.syncPendingCaptures();

      final updated = await dbHelper.getAllCaptures();
      expect(updated.first.retryCount, equals(11));
      expect(syncWorker.stuckPhotos, contains('loc-stuck-99'));
    });
  });
}
