import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/src/core/database/database_helper.dart';
import 'package:mobile/src/features/auth/data/auth_service.dart';
import 'package:mobile/src/features/scans/models/capture_record.dart';
import 'package:mobile/src/features/scans/services/verdict_sync_service.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const Map<String, dynamic> _userJson = {
  'id': 'officer-1',
  'username': 'lmo_test',
  'email': 'lmo_test@legalmetrology.gov.in',
  'full_name': 'Test Officer',
  'role': 'field_lmo',
  'district': 'Chennai, TN',
  'is_active': true,
};

Future<AuthService> _signedIn() async {
  final auth = AuthService.createTestInstance(
    client: MockClient((_) async => http.Response(
          jsonEncode({'access_token': 'jwt-1', 'token_type': 'bearer', 'user': _userJson}),
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
    db = await databaseFactoryFfi.openDatabase(inMemoryDatabasePath);
    await DatabaseHelper.createSchema(db);
    dbHelper = DatabaseHelper();
    dbHelper.setDatabase(db);
  });

  tearDown(() async => db.close());

  Future<void> seedSynced({
    required String localId,
    required String serverScanId,
    String? serverStatus,
  }) async {
    await dbHelper.insertCapture(CaptureRecord(
      localId: localId,
      capturedAtUtc: DateTime.now().toUtc().toIso8601String(),
      referenceObjectType: 'debit_card',
      syncStatus: 'SYNCED',
      serverScanId: serverScanId,
      serverStatus: serverStatus,
    ));
  }

  group('VerdictSyncService', () {
    test('records a FAILED verdict with the rules that were breached', () async {
      await seedSynced(localId: 'loc-1', serverScanId: 'scan-abc');

      final service = VerdictSyncService.createTestInstance(
        dbHelper: dbHelper,
        authService: await _signedIn(),
        client: MockClient((request) async {
          expect(request.url.path, contains('/scans/scan-abc'));
          expect(request.headers['Authorization'], 'Bearer jwt-1');
          return http.Response(
            jsonEncode({
              'status': 'FAILED',
              'rule_results': [
                {'rule_id': 'rule_6_1_e', 'status': 'FAIL', 'reason': 'MRP missing tax phrase'},
                {'rule_id': 'schedule_ii', 'status': 'FAIL', 'reason': 'Numerals below 4 mm'},
                {'rule_id': 'rule_6_1_a', 'status': 'PASS'},
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }),
      );

      expect(await service.refreshOnce(), equals(1));

      final record = await dbHelper.getCaptureById('loc-1');
      expect(record!.serverStatus, 'FAILED');
      expect(record.verdict, VerdictStatus.failed);
      // Only the failing rules are kept; a passing one is not a breach.
      expect(record.ruleFailures, equals(['rule_6_1_e', 'schedule_ii']));
      expect(record.verdictSummary, contains('rule_6_1_e'));
    });

    test('a PASSED verdict reads as compliant with no breaches', () async {
      await seedSynced(localId: 'loc-2', serverScanId: 'scan-pass');

      final service = VerdictSyncService.createTestInstance(
        dbHelper: dbHelper,
        authService: await _signedIn(),
        client: MockClient((_) async => http.Response(
              jsonEncode({'status': 'PASSED', 'rule_results': []}),
              200,
              headers: {'content-type': 'application/json'},
            )),
      );

      expect(await service.refreshOnce(), equals(1));
      final record = await dbHelper.getCaptureById('loc-2');
      expect(record!.verdict, VerdictStatus.passed);
      expect(record.ruleFailures, isEmpty);
    });

    test('a calibration failure tells the officer what to do about it', () async {
      await seedSynced(localId: 'loc-3', serverScanId: 'scan-cal');

      final service = VerdictSyncService.createTestInstance(
        dbHelper: dbHelper,
        authService: await _signedIn(),
        client: MockClient((_) async => http.Response(
              jsonEncode({'status': 'CALIBRATION_FAILED', 'rule_results': []}),
              200,
              headers: {'content-type': 'application/json'},
            )),
      );

      await service.refreshOnce();
      final record = await dbHelper.getCaptureById('loc-3');
      expect(record!.verdict, VerdictStatus.calibrationFailed);
      expect(record.verdictSummary, contains('Re-capture'));
    });

    test('a capture already holding a terminal verdict is not re-polled', () async {
      await seedSynced(localId: 'loc-4', serverScanId: 'scan-done', serverStatus: 'PASSED');

      var requestWasMade = false;
      final service = VerdictSyncService.createTestInstance(
        dbHelper: dbHelper,
        authService: await _signedIn(),
        client: MockClient((_) async {
          requestWasMade = true;
          return http.Response('{}', 200);
        }),
      );

      expect(await service.refreshOnce(), equals(0));
      expect(requestWasMade, isFalse);
    });

    test('signed out, it makes no requests at all', () async {
      await seedSynced(localId: 'loc-5', serverScanId: 'scan-x');

      var requestWasMade = false;
      final service = VerdictSyncService.createTestInstance(
        dbHelper: dbHelper,
        authService: AuthService.createTestInstance(),
        client: MockClient((_) async {
          requestWasMade = true;
          return http.Response('{}', 200);
        }),
      );

      expect(await service.refreshOnce(), equals(0));
      expect(requestWasMade, isFalse);
    });

    test('a 401 ends the session instead of looping on rejected requests', () async {
      await seedSynced(localId: 'loc-6', serverScanId: 'scan-401');
      final auth = await _signedIn();

      final service = VerdictSyncService.createTestInstance(
        dbHelper: dbHelper,
        authService: auth,
        client: MockClient((_) async => http.Response('{"detail":"expired"}', 401)),
      );

      await service.refreshOnce();
      expect(auth.isAuthenticated, isFalse);
    });

    test('a capture that never reached the server is skipped', () async {
      // ACK- ids are the local placeholder used when a response omits scan_id;
      // asking the server about one would 404 on every pass.
      await seedSynced(localId: 'loc-7', serverScanId: 'ACK-loc-7');

      var requestWasMade = false;
      final service = VerdictSyncService.createTestInstance(
        dbHelper: dbHelper,
        authService: await _signedIn(),
        client: MockClient((_) async {
          requestWasMade = true;
          return http.Response('{}', 200);
        }),
      );

      expect(await service.refreshOnce(), equals(0));
      expect(requestWasMade, isFalse);
    });
  });
}
