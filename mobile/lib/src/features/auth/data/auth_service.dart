import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
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
/// NOTE (Architectural Roadmap):
/// In this phase, authenticated sessions are managed in-memory.
/// In Phase 2.3 (Offline queue + background sync), this service will be wired
/// to `flutter_secure_storage` (backed by Android Keystore / iOS Keychain)
/// to ensure encrypted token persistence across app restarts.
class AuthService extends ChangeNotifier {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;

  AuthService._internal({http.Client? client}) : _client = client ?? http.Client();

  http.Client _client;

  @visibleForTesting
  void setClient(http.Client client) {
    _client = client;
  }

  AuthToken? _currentToken;
  User? _currentUser;
  bool _isOffline = false;

  AuthToken? get currentToken => _currentToken;
  User? get currentUser => _currentUser;
  bool get isAuthenticated => _currentToken != null && _currentUser != null;
  bool get isOffline => _isOffline;

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

  /// Explicitly logout current user and clear in-memory credentials
  void logout() {
    _currentToken = null;
    _currentUser = null;
    notifyListeners();
  }

  /// Sets offline mode state (e.g., when field network is unavailable)
  void setOffline(bool offline) {
    _isOffline = offline;
    notifyListeners();
  }
}
