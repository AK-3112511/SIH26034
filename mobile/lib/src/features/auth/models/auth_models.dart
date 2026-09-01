/// Authenticated LMO User Profile
/// Matches backend UserResponse schema (app.schemas.auth.UserResponse)
class User {
  final String id;
  final String username;
  final String email;
  final String fullName;
  final String role;
  final String? district;
  final bool isActive;
  final DateTime? createdAt;

  const User({
    required this.id,
    required this.username,
    required this.email,
    required this.fullName,
    required this.role,
    this.district,
    required this.isActive,
    this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String? ?? '',
      username: json['username'] as String? ?? '',
      email: json['email'] as String? ?? '',
      fullName: json['full_name'] as String? ?? '',
      role: json['role'] as String? ?? 'field_lmo',
      district: json['district'] as String?,
      isActive: json['is_active'] as bool? ?? true,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'email': email,
      'full_name': fullName,
      'role': role,
      'district': district,
      'is_active': isActive,
      'created_at': createdAt?.toIso8601String(),
    };
  }
}

/// Authentication Token Response
/// Matches backend TokenResponse schema (app.schemas.auth.TokenResponse)
class AuthToken {
  final String accessToken;
  final String tokenType;
  final User user;

  const AuthToken({
    required this.accessToken,
    required this.tokenType,
    required this.user,
  });

  factory AuthToken.fromJson(Map<String, dynamic> json) {
    return AuthToken(
      accessToken: json['access_token'] as String? ?? '',
      tokenType: json['token_type'] as String? ?? 'bearer',
      user: User.fromJson(json['user'] as Map<String, dynamic>? ?? {}),
    );
  }
}
