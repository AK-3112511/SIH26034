import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/src/core/config/app_config.dart';
import 'package:mobile/src/features/auth/data/auth_service.dart';

const Map<String, dynamic> _userJson = {
  'id': 'officer-1',
  'username': 'lmo_test',
  'email': 'lmo_test@legalmetrology.gov.in',
  'full_name': 'Test Officer',
  'role': 'field_lmo',
  'district': 'Chennai, TN',
  'is_active': true,
};

http.Response _loginOk() => http.Response(
      jsonEncode({'access_token': 'jwt-1', 'token_type': 'bearer', 'user': _userJson}),
      200,
      headers: {'content-type': 'application/json'},
    );

/// Secure storage is a platform channel and is unavailable on the test host, so
/// a signed-in AuthService is produced by logging in against a stub server
/// rather than by seeding storage.
Future<AuthService> _signedIn() async {
  final auth = AuthService.createTestInstance(
    client: MockClient((_) async => _loginOk()),
  );
  await auth.login(username: 'lmo_test', password: 'secret');
  expect(auth.isAuthenticated, isTrue);
  return auth;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AuthService', () {
    test('offers no password-less way in', () async {
      final auth = AuthService.createTestInstance(
        client: MockClient((_) async => throw const SocketException('offline')),
      );

      final result = await auth.login(username: 'lmo_test', password: 'secret');

      // Being offline reports a network error; it never fabricates a session.
      // A capture made under an invented identity could not be attributed to an
      // officer, which is the point of the Section 65B chain.
      expect(result.isSuccess, isFalse);
      expect(result.isNetworkError, isTrue);
      expect(auth.isAuthenticated, isFalse);
      expect(auth.currentUser, isNull);
    });

    test('empty credentials are rejected before any request', () async {
      var requestWasMade = false;
      final auth = AuthService.createTestInstance(
        client: MockClient((_) async {
          requestWasMade = true;
          return _loginOk();
        }),
      );

      expect((await auth.login(username: '', password: '')).isSuccess, isFalse);
      expect((await auth.login(username: 'lmo_test', password: '')).isSuccess, isFalse);
      expect(requestWasMade, isFalse);
    });

    test('restoreSession reports none when nothing is stored', () async {
      final auth = AuthService.createTestInstance(
        client: MockClient((_) async => http.Response('{}', 200)),
      );
      expect(await auth.restoreSession(), SessionRestoreOutcome.none);
    });

    test('a server-rejected token ends the session and explains why', () async {
      final auth = await _signedIn();
      auth.setClient(MockClient((_) async => http.Response('{"detail":"expired"}', 401)));

      expect(await auth.restoreSession(), SessionRestoreOutcome.expired);
      expect(auth.isAuthenticated, isFalse);
      expect(auth.sessionEndedReason, contains('session expired'));
    });

    test('an unreachable server keeps the cached session for field work', () async {
      final auth = await _signedIn();
      auth.setClient(MockClient((_) async => throw const SocketException('no route')));

      expect(await auth.restoreSession(), SessionRestoreOutcome.offlineCached);
      // The officer stays signed in: they authenticated for real on this device
      // previously, so queued captures remain attributable.
      expect(auth.isAuthenticated, isTrue);
      expect(auth.isOffline, isTrue);
    });

    test('a valid token adopts the server copy of the profile', () async {
      final auth = await _signedIn();
      auth.setClient(MockClient((_) async => http.Response(
            jsonEncode({..._userJson, 'district': 'Madurai', 'full_name': 'Transferred Officer'}),
            200,
            headers: {'content-type': 'application/json'},
          )));

      expect(await auth.restoreSession(), SessionRestoreOutcome.online);
      // A posting change made on the dashboard must reach the handset, because
      // district decides which queue an officer's work routes to.
      expect(auth.currentUser?.district, 'Madurai');
      expect(auth.currentUser?.fullName, 'Transferred Officer');
      expect(auth.isOffline, isFalse);
    });

    test('handleUnauthorized clears credentials mid-shift', () async {
      final auth = await _signedIn();
      await auth.handleUnauthorized();

      expect(auth.isAuthenticated, isFalse);
      expect(auth.token, isNull);
      expect(auth.authHeaders, isEmpty);
    });

    test('authHeaders carry the bearer token once signed in', () async {
      final auth = await _signedIn();
      expect(auth.authHeaders['Authorization'], 'Bearer jwt-1');
    });
  });

  group('AppConfig.normaliseBaseUrl', () {
    test('accepts what an officer would actually type', () {
      expect(AppConfig.normaliseBaseUrl('192.168.1.7:8000'), 'http://192.168.1.7:8000/api/v1');
      expect(AppConfig.normaliseBaseUrl('http://192.168.1.7:8000'), 'http://192.168.1.7:8000/api/v1');
      expect(AppConfig.normaliseBaseUrl('  10.0.2.2:8000/api/v1  '), 'http://10.0.2.2:8000/api/v1');
      expect(AppConfig.normaliseBaseUrl('https://metrology.gov.in'), 'https://metrology.gov.in/api/v1');
    });

    test('does not double up the api path or keep trailing slashes', () {
      expect(AppConfig.normaliseBaseUrl('http://host:8000/api/v1/'), 'http://host:8000/api/v1');
      expect(
        AppConfig.normaliseBaseUrl('http://host:8000/api/v1'),
        isNot(contains('/api/v1/api/v1')),
      );
    });

    test('rejects values that are not usable addresses', () {
      expect(AppConfig.normaliseBaseUrl(''), isNull);
      expect(AppConfig.normaliseBaseUrl('   '), isNull);
      expect(AppConfig.normaliseBaseUrl('ftp://host:21'), isNull);
      expect(AppConfig.normaliseBaseUrl('http://'), isNull);
    });
  });
}
