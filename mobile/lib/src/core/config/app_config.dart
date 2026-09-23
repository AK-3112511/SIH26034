import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../constants/api_constants.dart';

/// Device-scoped, non-secret settings: which server this handset talks to,
/// the stable identifier that goes into every Section 65B evidence hash, and
/// the officer's sync preference.
///
/// Secrets (the JWT) live in [AuthService]'s secure storage, never here.
///
/// Every accessor works before [load] completes and on hosts where the
/// `shared_preferences` platform channel is unavailable (unit tests, desktop),
/// falling back to in-memory defaults rather than throwing.
class AppConfig extends ChangeNotifier {
  static final AppConfig _instance = AppConfig._internal();
  factory AppConfig() => _instance;
  AppConfig._internal();

  @visibleForTesting
  factory AppConfig.createTestInstance() => AppConfig._internal();

  static const String _kBaseUrlKey = 'metrologyai_base_url';
  static const String _kDeviceIdKey = 'metrologyai_device_id';
  static const String _kWifiOnlyKey = 'metrologyai_wifi_only_sync';

  SharedPreferences? _prefs;
  bool _isLoaded = false;

  String _baseUrl = ApiConstants.defaultBaseUrl;
  String _deviceId = '';
  bool _wifiOnlySync = false;

  bool get isLoaded => _isLoaded;

  /// Base URL of the MetrologyAI API, e.g. `http://192.168.1.7:8000/api/v1`.
  String get baseUrl => _baseUrl;

  /// Stable per-installation identifier. Generated once and persisted, because
  /// the Section 65B hash binds image|lat|lng|timestamp|device_id — a value that
  /// changed per capture would make every hash unverifiable after the fact.
  String get deviceId => _deviceId;

  /// When true, WorkManager only runs background uploads on unmetered networks.
  bool get wifiOnlySync => _wifiOnlySync;

  Future<void> load() async {
    try {
      _prefs = await SharedPreferences.getInstance();
    } catch (e) {
      debugPrint('[AppConfig] Preferences unavailable (expected in tests): $e');
    }

    final stored = _prefs?.getString(_kBaseUrlKey);
    if (stored != null && stored.trim().isNotEmpty) {
      _baseUrl = stored.trim();
    }

    var deviceId = _prefs?.getString(_kDeviceIdKey);
    if (deviceId == null || deviceId.isEmpty) {
      deviceId = 'lmo-${const Uuid().v4()}';
      await _write(() => _prefs?.setString(_kDeviceIdKey, deviceId!));
    }
    _deviceId = deviceId;

    _wifiOnlySync = _prefs?.getBool(_kWifiOnlyKey) ?? false;

    ApiConstants.baseUrl = _baseUrl;
    _isLoaded = true;
    notifyListeners();
  }

  /// Validates and persists a new server address. Returns an error message when
  /// the value is not a usable absolute http(s) URL, or null on success.
  Future<String?> setBaseUrl(String value) async {
    final normalised = normaliseBaseUrl(value);
    if (normalised == null) {
      return 'Enter a full server address, for example http://192.168.1.7:8000';
    }

    _baseUrl = normalised;
    ApiConstants.baseUrl = normalised;
    await _write(() => _prefs?.setString(_kBaseUrlKey, normalised));
    notifyListeners();
    return null;
  }

  Future<void> setWifiOnlySync(bool value) async {
    _wifiOnlySync = value;
    await _write(() => _prefs?.setBool(_kWifiOnlyKey, value));
    notifyListeners();
  }

  Future<void> _write(Future<bool>? Function() op) async {
    try {
      await op();
    } catch (e) {
      debugPrint('[AppConfig] Could not persist preference: $e');
    }
  }

  /// Accepts what an officer would actually type — `192.168.1.7:8000`,
  /// `http://host:8000`, or a full `.../api/v1` path — and returns the
  /// canonical API root, or null if it cannot be made into one.
  static String? normaliseBaseUrl(String raw) {
    var value = raw.trim();
    if (value.isEmpty) return null;

    if (!value.contains('://')) {
      value = 'http://$value';
    }

    final uri = Uri.tryParse(value);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) return null;
    if (uri.scheme != 'http' && uri.scheme != 'https') return null;

    var path = uri.path.replaceAll(RegExp(r'/+$'), '');
    if (!path.endsWith('/api/v1')) {
      path = '$path/api/v1';
    }

    // Build the URI explicitly rather than using `replace(query: '', ...)`,
    // which emits a trailing "?#".
    return Uri(
      scheme: uri.scheme,
      host: uri.host,
      port: uri.hasPort ? uri.port : null,
      path: path,
    ).toString();
  }
}
