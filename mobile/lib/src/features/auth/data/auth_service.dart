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

/// Authentication Service
/// Handles communication with FastAPI /auth/login endpoint.
///
/// On successful login, the JWT is persisted via `flutter_secure_storage`
/// (Android Keystore / iOS Keychain) so the LMO remains authenticated across
/// app restarts without re-entering credentials in the field.
/// In host-only test environments where the secure-storage platform plugin is
/// not available, all storage calls are silently skipped — authentication state
/// still works in-memory for the duration of the test.
class AuthService extends ChangeNotifier {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;

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

  AuthToken? get currentToken => _currentToken;
  User? get currentUser => _currentUser;
  bool get isAuthenticated => _currentToken != null && _currentUser != null;
  bool get isOffline => _isOffline;

  /// Load a previously persisted JWT token from secure storage (call at app start).
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

        // Persist JWT to device secure storage (Android Keystore / iOS Keychain).
        // Fire-and-forget: does not block login() — platform channel may be unavailable in tests.
        _secureStorage.write(key: _kTokenKey, value: authToken.accessToken).catchError((_) {});
        if (_currentUser != null) {
          _secureStorage.write(
            key: _kUserKey,
            value: jsonEncode(_currentUser!.toJson()),
          ).catchError((_) {});
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

  /// Authenticate in offline field mode when central server is unreachable (§2 Screen 1)
  ///
  /// NOTE: No default username is assumed — the LMO must supply their own identifier.
  /// No hardcoded demo credentials or named personas exist in this path.
  AuthResult loginOffline({
    required String username,
    String? district,
  }) {
    final trimmedUser = username.trim().isEmpty ? 'field_officer' : username.trim();
    final user = User(
      id: 'offline-lmo-session',
      username: trimmedUser,
      email: '$trimmedUser@legalmetrology.gov.in',
      fullName: 'Field Officer',
      role: 'field_lmo',
      district: district ?? 'Unknown District',
      isActive: true,
      createdAt: DateTime.now(),
    );

    _currentToken = AuthToken(
      accessToken: 'offline-session-token',
      tokenType: 'bearer',
      user: user,
    );
    _currentUser = user;
    _isOffline = true;
    notifyListeners();
    return AuthResult.success(user);
  }

  /// Logout: clear in-memory credentials and wipe persisted token from secure storage.
  /// State is cleared synchronously so navigation can proceed immediately.
  /// Secure storage deletion is fire-and-forget (does not block navigation).
  Future<void> logout() async {
    _currentToken = null;
    _currentUser = null;
    notifyListeners();
    // Secure storage cleanup is best-effort and non-blocking
    _secureStorage.delete(key: _kTokenKey).catchError((_) {});
    _secureStorage.delete(key: _kUserKey).catchError((_) {});
  }

  /// Sets offline mode state (e.g., when field network is unavailable)
  void setOffline(bool offline) {
    _isOffline = offline;
    notifyListeners();
  }
}
