import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

/// Why a capture could not be located. Each case has a distinct remedy, so the
/// capture screen can tell the officer what to actually do about it.
enum LocationFailure {
  serviceDisabled,
  permissionDenied,
  permissionDeniedForever,
  timeout,
  unavailable,
}

/// A GPS fix, or the reason there isn't one.
class LocationResult {
  final double? latitude;
  final double? longitude;
  final double? accuracyMetres;
  final LocationFailure? failure;

  const LocationResult.success({
    required double this.latitude,
    required double this.longitude,
    this.accuracyMetres,
  }) : failure = null;

  const LocationResult.failed(this.failure)
      : latitude = null,
        longitude = null,
        accuracyMetres = null;

  bool get isSuccess => failure == null && latitude != null && longitude != null;

  /// Plain-language explanation for the officer, naming the fix.
  String get message {
    switch (failure) {
      case LocationFailure.serviceDisabled:
        return 'Location is switched off on this device. Turn on GPS to record where this package was inspected.';
      case LocationFailure.permissionDenied:
        return 'MetrologyAI needs location access to stamp this capture with the inspection site.';
      case LocationFailure.permissionDeniedForever:
        return 'Location access is blocked for MetrologyAI. Enable it in Android Settings > Apps > MetrologyAI > Permissions.';
      case LocationFailure.timeout:
        return 'Could not get a GPS fix. Move somewhere with a clearer view of the sky and try again.';
      case LocationFailure.unavailable:
        return 'Location is unavailable on this device.';
      case null:
        return 'Location acquired.';
    }
  }

  /// True when asking again could plausibly succeed (so the UI offers Retry).
  bool get isRetryable =>
      failure == LocationFailure.timeout ||
      failure == LocationFailure.permissionDenied ||
      failure == LocationFailure.serviceDisabled;
}

/// Thin wrapper over `geolocator` so the capture screen depends on an
/// injectable seam rather than platform channels, and so the whole
/// permission dance lives in one place.
///
/// The Section 65B evidence hash is computed over
/// `image | lat | lng | timestamp | device_id`. A hardcoded coordinate would
/// make that hash attest to a location the inspection never happened at, so a
/// capture without a real fix is refused rather than silently faked.
class LocationService {
  static final LocationService _instance = LocationService._internal();
  factory LocationService() => _instance;
  LocationService._internal();

  @visibleForTesting
  factory LocationService.createTestInstance() => LocationService._internal();

  /// Overridable hooks so widget tests can exercise every branch without a
  /// platform channel.
  @visibleForTesting
  Future<bool> Function()? isServiceEnabledOverride;
  @visibleForTesting
  Future<LocationPermission> Function()? checkPermissionOverride;
  @visibleForTesting
  Future<LocationPermission> Function()? requestPermissionOverride;
  @visibleForTesting
  Future<Position> Function()? getPositionOverride;

  @visibleForTesting
  void resetOverrides() {
    isServiceEnabledOverride = null;
    checkPermissionOverride = null;
    requestPermissionOverride = null;
    getPositionOverride = null;
  }

  /// Ask for a fix, requesting permission if it has not been granted yet.
  Future<LocationResult> getCurrentLocation({
    Duration timeout = const Duration(seconds: 12),
  }) async {
    try {
      final serviceEnabled =
          await (isServiceEnabledOverride ?? Geolocator.isLocationServiceEnabled)();
      if (!serviceEnabled) {
        return const LocationResult.failed(LocationFailure.serviceDisabled);
      }

      var permission = await (checkPermissionOverride ?? Geolocator.checkPermission)();
      if (permission == LocationPermission.denied) {
        permission = await (requestPermissionOverride ?? Geolocator.requestPermission)();
      }

      if (permission == LocationPermission.deniedForever) {
        return const LocationResult.failed(LocationFailure.permissionDeniedForever);
      }
      if (permission == LocationPermission.denied) {
        return const LocationResult.failed(LocationFailure.permissionDenied);
      }

      final position = await (getPositionOverride ??
              () => Geolocator.getCurrentPosition(
                    locationSettings: LocationSettings(
                      accuracy: LocationAccuracy.high,
                      timeLimit: timeout,
                    ),
                  ))()
          .timeout(timeout);

      return LocationResult.success(
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyMetres: position.accuracy,
      );
    } on TimeoutException catch (_) {
      return const LocationResult.failed(LocationFailure.timeout);
    } catch (e) {
      debugPrint('[LocationService] Could not obtain a fix: $e');
      return const LocationResult.failed(LocationFailure.unavailable);
    }
  }

  /// Opens the OS app-settings page so a permanently denied permission can be
  /// re-granted without the officer hunting through Settings.
  Future<bool> openPermissionSettings() async {
    try {
      return await Geolocator.openAppSettings();
    } catch (e) {
      debugPrint('[LocationService] Could not open app settings: $e');
      return false;
    }
  }
}
