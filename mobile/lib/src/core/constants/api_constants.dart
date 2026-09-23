class ApiConstants {
  ApiConstants._();

  /// Default host: 127.0.0.1:8000 works with `adb reverse tcp:8000 tcp:8000`
  /// over USB. On a LAN the officer sets the real address in Settings, which
  /// `AppConfig.load()` then writes into [baseUrl] at boot.
  static const String defaultBaseUrl = 'http://127.0.0.1:8000/api/v1';

  /// Current API root. Owned by `AppConfig` — set it through
  /// `AppConfig().setBaseUrl()` so the change is persisted, not directly.
  static String baseUrl = defaultBaseUrl;

  static String get loginEndpoint => '$baseUrl/auth/login';
  static String get meEndpoint => '$baseUrl/auth/me';
  static String get scansIngestEndpoint => '$baseUrl/scans/ingest';
  static String get eventsPollEndpoint => '$baseUrl/events/poll';
  static String get scansAssignedToMeEndpoint => '$baseUrl/scans/assigned-to-me';
  static String scanDetailEndpoint(String scanId) => '$baseUrl/scans/$scanId';
}
