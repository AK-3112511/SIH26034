import 'dart:convert';

import '../../../core/widgets/status_chip.dart';

/// The verdict the backend reached for a capture, once it has one.
/// Distinct from [CaptureRecord.syncStatus], which only describes whether the
/// photo made it off the handset.
enum VerdictStatus {
  /// Server has not finished processing (or we have not asked yet).
  awaiting,
  passed,
  failed,
  pendingReview,
  calibrationFailed,
  processingFailed;

  static VerdictStatus fromServer(String? raw) {
    switch (raw?.toUpperCase()) {
      case 'PASSED':
        return VerdictStatus.passed;
      case 'FAILED':
        return VerdictStatus.failed;
      case 'PENDING_REVIEW':
        return VerdictStatus.pendingReview;
      case 'CALIBRATION_FAILED':
      case 'LOW_CONFIDENCE_CALIBRATION':
        return VerdictStatus.calibrationFailed;
      case 'PROCESSING_FAILED':
        return VerdictStatus.processingFailed;
      default:
        return VerdictStatus.awaiting;
    }
  }

  /// True once the backend will not change its mind on its own.
  bool get isTerminal => this != VerdictStatus.awaiting;

  String get label {
    switch (this) {
      case VerdictStatus.awaiting:
        return 'Awaiting verdict';
      case VerdictStatus.passed:
        return 'Compliant';
      case VerdictStatus.failed:
        return 'Non-compliant';
      case VerdictStatus.pendingReview:
        return 'Under review';
      case VerdictStatus.calibrationFailed:
        return 'Could not measure';
      case VerdictStatus.processingFailed:
        return 'Processing error';
    }
  }
}

/// Representation of a local capture entity in SQLite
class CaptureRecord {
  final String localId;
  final String? imagePath;
  final double? lat;
  final double? lng;
  final double? accuracyMetres;
  final String capturedAtUtc;

  /// The calibration reference placed in frame: 'debit_card' | 'pan_card'.
  /// This is what gives the pipeline its mm-per-pixel scale.
  final String referenceObjectType;

  /// The package geometry: 'box' | 'bottle' | 'other'. Drives dewarping, and
  /// is a different question from which card was used as the ruler.
  final String productType;

  /// Optional brand / product typed by the officer at review time.
  final String? productName;

  final String? deviceId;
  final String syncStatus; // 'PENDING_UPLOAD' | 'UPLOADING' | 'SYNCED' | 'FAILED'
  final int retryCount;
  final String? nextAttemptAtUtc;
  final String? lastError;
  final String? serverScanId;
  final String? serverStatus;
  final String? verdictSummary;
  final String? ruleFailuresJson;

  const CaptureRecord({
    required this.localId,
    this.imagePath,
    this.lat,
    this.lng,
    this.accuracyMetres,
    required this.capturedAtUtc,
    required this.referenceObjectType,
    this.productType = 'box',
    this.productName,
    this.deviceId,
    required this.syncStatus,
    this.retryCount = 0,
    this.nextAttemptAtUtc,
    this.lastError,
    this.serverScanId,
    this.serverStatus,
    this.verdictSummary,
    this.ruleFailuresJson,
  });

  /// Map sync_status string to the UI SyncStatus enum.
  SyncStatus get toUiSyncStatus {
    switch (syncStatus.toUpperCase()) {
      case 'SYNCED':
        return SyncStatus.synced;
      case 'PENDING_UPLOAD':
      case 'UPLOADING':
        return SyncStatus.pendingUpload;
      case 'FAILED':
      default:
        return SyncStatus.failed;
    }
  }

  VerdictStatus get verdict => VerdictStatus.fromServer(serverStatus);

  bool get isSynced => syncStatus.toUpperCase() == 'SYNCED';

  /// Rule ids the backend found in violation, decoded from the stored JSON.
  List<String> get ruleFailures {
    if (ruleFailuresJson == null || ruleFailuresJson!.isEmpty) return const [];
    try {
      final decoded = jsonDecode(ruleFailuresJson!);
      if (decoded is List) {
        return decoded.map((e) => e.toString()).toList();
      }
    } catch (_) {
      // Corrupt payload is not worth crashing a list tile over.
    }
    return const [];
  }

  Map<String, dynamic> toMap() {
    return {
      'local_id': localId,
      'image_path': imagePath,
      'lat': lat,
      'lng': lng,
      'accuracy_m': accuracyMetres,
      'captured_at_utc': capturedAtUtc,
      'reference_object_type': referenceObjectType,
      'product_type': productType,
      'product_name': productName,
      'device_id': deviceId,
      'sync_status': syncStatus,
      'retry_count': retryCount,
      'next_attempt_at_utc': nextAttemptAtUtc,
      'last_error': lastError,
      'server_scan_id': serverScanId,
      'server_status': serverStatus,
      'verdict_summary': verdictSummary,
      'rule_failures': ruleFailuresJson,
    };
  }

  factory CaptureRecord.fromMap(Map<String, dynamic> map) {
    return CaptureRecord(
      localId: map['local_id'] as String,
      imagePath: map['image_path'] as String?,
      lat: (map['lat'] as num?)?.toDouble(),
      lng: (map['lng'] as num?)?.toDouble(),
      accuracyMetres: (map['accuracy_m'] as num?)?.toDouble(),
      capturedAtUtc: map['captured_at_utc'] as String,
      referenceObjectType: map['reference_object_type'] as String? ?? 'debit_card',
      productType: map['product_type'] as String? ?? 'box',
      productName: map['product_name'] as String?,
      deviceId: map['device_id'] as String?,
      syncStatus: map['sync_status'] as String? ?? 'PENDING_UPLOAD',
      retryCount: (map['retry_count'] as num?)?.toInt() ?? 0,
      nextAttemptAtUtc: map['next_attempt_at_utc'] as String?,
      lastError: map['last_error'] as String?,
      serverScanId: map['server_scan_id'] as String?,
      serverStatus: map['server_status'] as String?,
      verdictSummary: map['verdict_summary'] as String?,
      ruleFailuresJson: map['rule_failures'] as String?,
    );
  }

  CaptureRecord copyWith({
    String? localId,
    String? imagePath,
    double? lat,
    double? lng,
    double? accuracyMetres,
    String? capturedAtUtc,
    String? referenceObjectType,
    String? productType,
    String? productName,
    String? deviceId,
    String? syncStatus,
    int? retryCount,
    String? nextAttemptAtUtc,
    String? lastError,
    String? serverScanId,
    String? serverStatus,
    String? verdictSummary,
    String? ruleFailuresJson,
    bool clearImagePath = false,
  }) {
    return CaptureRecord(
      localId: localId ?? this.localId,
      imagePath: clearImagePath ? null : (imagePath ?? this.imagePath),
      lat: lat ?? this.lat,
      lng: lng ?? this.lng,
      accuracyMetres: accuracyMetres ?? this.accuracyMetres,
      capturedAtUtc: capturedAtUtc ?? this.capturedAtUtc,
      referenceObjectType: referenceObjectType ?? this.referenceObjectType,
      productType: productType ?? this.productType,
      productName: productName ?? this.productName,
      deviceId: deviceId ?? this.deviceId,
      syncStatus: syncStatus ?? this.syncStatus,
      retryCount: retryCount ?? this.retryCount,
      nextAttemptAtUtc: nextAttemptAtUtc ?? this.nextAttemptAtUtc,
      lastError: lastError ?? this.lastError,
      serverScanId: serverScanId ?? this.serverScanId,
      serverStatus: serverStatus ?? this.serverStatus,
      verdictSummary: verdictSummary ?? this.verdictSummary,
      ruleFailuresJson: ruleFailuresJson ?? this.ruleFailuresJson,
    );
  }
}
