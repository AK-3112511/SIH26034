import '../../../core/widgets/status_chip.dart';

/// Representation of a local capture entity in SQLite
/// Source: MetrologyAI_Elevated_Blueprint.md §3.1
class CaptureRecord {
  final String localId;
  final String? imagePath;
  final double? lat;
  final double? lng;
  final String capturedAtUtc;
  final String referenceObjectType; // 'debit_card' | 'pan_card' | 'manual'
  final String syncStatus; // 'PENDING_UPLOAD' | 'UPLOADING' | 'SYNCED' | 'FAILED'
  final int retryCount;
  final String? serverScanId;

  const CaptureRecord({
    required this.localId,
    this.imagePath,
    this.lat,
    this.lng,
    required this.capturedAtUtc,
    required this.referenceObjectType,
    required this.syncStatus,
    this.retryCount = 0,
    this.serverScanId,
  });

  /// Map sync_status string to UI SyncStatus enum (§5.4)
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

  Map<String, dynamic> toMap() {
    return {
      'local_id': localId,
      'image_path': imagePath,
      'lat': lat,
      'lng': lng,
      'captured_at_utc': capturedAtUtc,
      'reference_object_type': referenceObjectType,
      'sync_status': syncStatus,
      'retry_count': retryCount,
      'server_scan_id': serverScanId,
    };
  }

  factory CaptureRecord.fromMap(Map<String, dynamic> map) {
    return CaptureRecord(
      localId: map['local_id'] as String,
      imagePath: map['image_path'] as String?,
      lat: (map['lat'] as num?)?.toDouble(),
      lng: (map['lng'] as num?)?.toDouble(),
      capturedAtUtc: map['captured_at_utc'] as String,
      referenceObjectType: map['reference_object_type'] as String? ?? 'debit_card',
      syncStatus: map['sync_status'] as String? ?? 'PENDING_UPLOAD',
      retryCount: (map['retry_count'] as num?)?.toInt() ?? 0,
      serverScanId: map['server_scan_id'] as String?,
    );
  }

  CaptureRecord copyWith({
    String? localId,
    String? imagePath,
    double? lat,
    double? lng,
    String? capturedAtUtc,
    String? referenceObjectType,
    String? syncStatus,
    int? retryCount,
    String? serverScanId,
    bool clearImagePath = false,
  }) {
    return CaptureRecord(
      localId: localId ?? this.localId,
      imagePath: clearImagePath ? null : (imagePath ?? this.imagePath),
      lat: lat ?? this.lat,
      lng: lng ?? this.lng,
      capturedAtUtc: capturedAtUtc ?? this.capturedAtUtc,
      referenceObjectType: referenceObjectType ?? this.referenceObjectType,
      syncStatus: syncStatus ?? this.syncStatus,
      retryCount: retryCount ?? this.retryCount,
      serverScanId: serverScanId ?? this.serverScanId,
    );
  }
}
