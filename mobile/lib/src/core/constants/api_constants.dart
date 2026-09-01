class ApiConstants {
  ApiConstants._();

  /// Default host: 127.0.0.1:8000 (compatible with adb reverse on USB devices and local development)
  static const String defaultBaseUrl = 'http://127.0.0.1:8000/api/v1';

  /// Mutable base URL override (e.g. for testing against remote backend, emulator 10.0.2.2, or LAN IP)
  static String baseUrl = defaultBaseUrl;

  static String get loginEndpoint => '$baseUrl/auth/login';
  static String get meEndpoint => '$baseUrl/auth/me';
  static String get scansIngestEndpoint => '$baseUrl/scans/ingest';
}
