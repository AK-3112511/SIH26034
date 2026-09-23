import '../../../core/widgets/status_chip.dart';
import 'capture_record.dart';

enum CaptureOrigin {
  selfCaptured,
  assignedTask,
}

/// A row on the Home screen: either a capture taken on this device or a
/// follow-up task assigned from the dashboard.
///
/// [syncStatus] answers "did the photo leave the handset" and [verdict]
/// answers "what did the system decide". They are deliberately separate
/// fields, and are rendered with deliberately different shapes.
class CaptureItem {
  final String id;

  /// Local SQLite key, when this row is a capture from this device. Null for
  /// assigned tasks, which have no local capture row.
  final String? localId;

  final String productName;
  final String category;
  final DateTime timestamp;
  final String location;
  final SyncStatus syncStatus;
  final VerdictStatus verdict;
  final CaptureOrigin origin;
  final String? platform;
  final String? taskType;
  final String? assignedBy;
  final String? followUpNote;

  const CaptureItem({
    required this.id,
    this.localId,
    required this.productName,
    required this.category,
    required this.timestamp,
    required this.location,
    required this.syncStatus,
    this.verdict = VerdictStatus.awaiting,
    this.origin = CaptureOrigin.selfCaptured,
    this.platform,
    this.taskType,
    this.assignedBy,
    this.followUpNote,
  });

  bool get isAssignedTask => origin == CaptureOrigin.assignedTask;
}
