import 'dart:io' show Platform;
import 'package:flutter/foundation.dart';

class ApiConstants {
  ApiConstants._();

  /// Default host detection: Android emulator routes 10.0.2.2 to host machine localhost,
  /// desktop and other targets use 127.0.0.1.
  static String get defaultBaseUrl {
    if (!kIsWeb && Platform.isAndroid) {
      return 'http://10.0.2.2:8000/api/v1';
    }
    return 'http://127.0.0.1:8000/api/v1';
  }

  /// Mutable base URL override (e.g. for testing against remote backend or custom host)
  static String baseUrl = defaultBaseUrl;

  static String get loginEndpoint => '$baseUrl/auth/login';
  static String get meEndpoint => '$baseUrl/auth/me';
  static String get scansIngestEndpoint => '$baseUrl/scans/ingest';
}
