import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import '../../../core/constants/api_constants.dart';
import '../models/auth_models.dart';

/// Authentication Result wrapper
class AuthResult {
  final bool isSuccess;
  final String? errorMessage;
  final bool isNetworkError;
  final User? user;

  const AuthResult.success(this.user)
      : isSuccess = true,
        errorMessage = null,
        isNetworkError = false;

  const AuthResult.failure(this.errorMessage, {this.isNetworkError = false})
      : isSuccess = false,
        user = null;
}

/// What happened when the app tried to resume a previous session at boot.
enum SessionRestoreOutcome {
  /// Nothing was stored - show the login screen.
  none,

  /// A stored token was accepted by the server; the officer is fully online.
  online,

  /// The server could not be reached, but a previously authenticated session
  /// is cached on this device. The officer may keep capturing offline.
  offlineCached,

  /// The stored token was rejected. Credentials have been wiped; re-login.
  expired,
}

/// Authentication Service
/// Handles communication with FastAPI /auth/login endpoint.
///
/// On successful login the JWT is persisted via `flutter_secure_storage`
/// (Android Keystore / iOS Keychain) so the LMO remains authenticated across
/// app restarts without re-entering credentials in the field.
///
/// There is deliberately no password-less path. Working offline requires a
/// session this device previously obtained from the server with real
/// credentials; see [restoreSession]. Evidence captured under a fabricated
/// identity would not be attributable to an officer, which is the whole point
/// of the Section 65B chain.
///
/// In host-only test environments where the secure-storage platform plugin is
/// not available, all storage calls are silently skipped - authentication state
/// still works in-memory for the duration of the test.
class AuthService extends ChangeNotifier {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;

  @visibleForTesting
  factory AuthService.createTestInstance({
    http.Client? client,
    FlutterSecureStorage? secureStorage,
  }) {
    return AuthService._internal(client: client, secureStorage: secureStorage);
  }

  AuthService._internal({http.Client? client, FlutterSecureStorage? secureStorage})
      : _client = client ?? http.Client(),
        _secureStorage = secureStorage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
            );

  http.Client _client;
  FlutterSecureStorage _secureStorage;

  static const String _kTokenKey = 'metrologyai_access_token';
  static const String _kUserKey = 'metrologyai_user_json';

  @visibleForTesting
  void setClient(http.Client client) {
    _client = client;
  }

  @visibleForTesting
  void setSecureStorage(FlutterSecureStorage storage) {
    _secureStorage = storage;
  }

  AuthToken? _currentToken;
  User? _currentUser;
  bool _isOffline = false;
  String? _sessionEndedReason;

  AuthToken? get currentToken => _currentToken;
  String? get token => _currentToken?.accessToken;
  User? get currentUser => _currentUser;
  bool get isAuthenticated => _currentToken != null && _currentUser != null;
  bool get isOffline => _isOffline;

  /// Set when a session was terminated by the server rather than by the user,
  /// so the login screen can explain why the officer is back there.
  String? get sessionEndedReason => _sessionEndedReason;

  void clearSessionEndedReason() {
    _sessionEndedReason = null;
  }

  /// Authorization header for any authenticated call. Empty when signed out,
  /// so callers can spread it unconditionally.
  Map<String, String> get authHeaders {
    final accessToken = _currentToken?.accessToken;
    if (accessToken == null) return const {};
    return {'Authorization': 'Bearer $accessToken'};
  }

  /// Load a previously persisted JWT token from secure storage.
  /// Silently no-ops in non-platform (test) environments.
  Future<void> loadStoredToken() async {
    try {
      final storedToken = await _secureStorage.read(key: _kTokenKey);
      final storedUserJson = await _secureStorage.read(key: _kUserKey);
      if (storedToken != null && storedUserJson != null) {
        final userMap = jsonDecode(storedUserJson) as Map<String, dynamic>;
        _currentUser = User.fromJson(userMap);
        _currentToken = AuthToken(
          accessToken: storedToken,
          tokenType: 'bearer',
          user: _currentUser!,
        );
        notifyListeners();
      }
    } catch (e) {
      debugPrint('[AuthService] Secure storage unavailable (expected in tests): $e');
    }
  }

  /// Resume a previous session at app start.
  ///
  /// A cached token is only trusted after the server confirms it is still
  /// valid. If the server cannot be reached we fall back to the cached session
  /// so field work continues in a dead zone, but if the server actively
  /// rejects the token the session is wiped.
  Future<SessionRestoreOutcome> restoreSession() async {
    await loadStoredToken();
    if (!isAuthenticated) return SessionRestoreOutcome.none;

    try {
      final response = await _client.get(
        Uri.parse(ApiConstants.meEndpoint),
        headers: {'Accept': 'application/json', ...authHeaders},
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        // Adopt the server's copy of the profile: role, district or active flag
        // may have changed since this device last logged in.
        try {
          final body = jsonDecode(response.body) as Map<String, dynamic>;
          final refreshed = User.fromJson(body);
          _currentUser = refreshed;
          _currentToken = AuthToken(
            accessToken: _currentToken!.accessToken,
            tokenType: _currentToken!.tokenType,
            user: refreshed,
          );
          unawaited(_persistUser(refreshed));
        } catch (e) {
          debugPrint('[AuthService] /auth/me returned an unreadable profile: $e');
        }
        _isOffline = false;
        notifyListeners();
        return SessionRestoreOutcome.online;
      }

      if (response.statusCode == 401 || response.statusCode == 403) {
        await _endSession('Your session expired. Please sign in again.');
        return SessionRestoreOutcome.expired;
      }

      // 5xx or anything else: the server is up but unhealthy. Keep the cached
      // session rather than locking an officer out of the field over a blip.
      debugPrint('[AuthService] /auth/me returned HTTP ${response.statusCode}; keeping cached session.');
      _isOffline = true;
      notifyListeners();
      return SessionRestoreOutcome.offlineCached;
    } on SocketException catch (_) {
      return _cachedOffline();
    } on http.ClientException catch (_) {
      return _cachedOffline();
    } on TimeoutException catch (_) {
      return _cachedOffline();
    } catch (e) {
      debugPrint('[AuthService] Unexpected error validating session: $e');
      return _cachedOffline();
    }
  }

  SessionRestoreOutcome _cachedOffline() {
    _isOffline = true;
    notifyListeners();
    return SessionRestoreOutcome.offlineCached;
  }

  /// Authenticate an LMO user against the backend /auth/login endpoint
  Future<AuthResult> login({
    required String username,
    required String password,
  }) async {
    final trimmedUser = username.trim();
    if (trimmedUser.isEmpty || password.isEmpty) {
      return const AuthResult.failure('Username/email and password are required');
    }

    final url = Uri.parse(ApiConstants.loginEndpoint);

    try {
      final response = await _client.post(
        url,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: jsonEncode({
          'username': trimmedUser,
          'password': password,
        }),
      ).timeout(const Duration(seconds: 10));

      _isOffline = false;

      if (response.statusCode == 200) {
        final Map<String, dynamic> body = jsonDecode(response.body) as Map<String, dynamic>;
        final authToken = AuthToken.fromJson(body);
        _currentToken = authToken;
        _currentUser = authToken.user;
        _sessionEndedReason = null;

        // Persist JWT to device secure storage (Android Keystore / iOS Keychain).
        // Fire-and-forget: does not block login() - platform channel may be unavailable in tests.
        _secureStorage.write(key: _kTokenKey, value: authToken.accessToken).catchError((_) {});
        if (_currentUser != null) {
          unawaited(_persistUser(_currentUser!));
        }

        notifyListeners();
        return AuthResult.success(_currentUser);
      } else {
        String errorMsg = 'Authentication failed (HTTP ${response.statusCode})';
        try {
          final errorBody = jsonDecode(response.body) as Map<String, dynamic>;
          if (errorBody.containsKey('detail')) {
            errorMsg = errorBody['detail'].toString();
          }
        } catch (_) {}
        return AuthResult.failure(errorMsg);
      }
    } on SocketException catch (_) {
      _isOffline = true;
      notifyListeners();
      return const AuthResult.failure(
        'Cannot connect to MetrologyAI server. Server is unreachable or device is offline.',
        isNetworkError: true,
      );
    } on http.ClientException catch (_) {
      _isOffline = true;
      notifyListeners();
      return const AuthResult.failure(
        'Network error encountered while connecting to authentication service.',
        isNetworkError: true,
      );
    } on TimeoutException catch (_) {
      _isOffline = true;
      notifyListeners();
      return const AuthResult.failure(
        'Authentication request timed out. Please check your connection.',
        isNetworkError: true,
      );
    } catch (e) {
      return AuthResult.failure('Unexpected error during login: $e');
    }
  }

  /// Called by any authenticated request that receives a 401, so a token
  /// revoked or expired mid-shift drops the officer back to the login screen
  /// instead of silently failing every upload.
  Future<void> handleUnauthorized() async {
    if (!isAuthenticated) return;
    await _endSession('Your session expired. Please sign in again.');
  }

  /// Logout: clear in-memory credentials and wipe persisted token from secure storage.
  Future<void> logout() async {
    await _endSession(null);
  }

  Future<void> _endSession(String? reason) async {
    _currentToken = null;
    _currentUser = null;
    _sessionEndedReason = reason;
    notifyListeners();
    // Secure storage cleanup is best-effort and non-blocking
    _secureStorage.delete(key: _kTokenKey).catchError((_) {});
    _secureStorage.delete(key: _kUserKey).catchError((_) {});
  }

  Future<void> _persistUser(User user) async {
    try {
      await _secureStorage.write(key: _kUserKey, value: jsonEncode(user.toJson()));
    } catch (_) {
      // Non-platform environment; in-memory state is still correct.
    }
  }

  /// Sets offline mode state (e.g., when field network is unavailable)
  void setOffline(bool offline) {
    _isOffline = offline;
    notifyListeners();
  }
}
