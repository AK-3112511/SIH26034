import '../../../core/widgets/status_chip.dart';

enum CaptureOrigin {
  selfCaptured,
  assignedTask,
}

/// Representation of a captured package inspection item or assigned task
/// Used on the Home Screen (§2, Screen 2) and offline sync queue.
class CaptureItem {
  final String id;
  final String productName;
  final String category;
  final DateTime timestamp;
  final String location;
  final SyncStatus syncStatus;
  final CaptureOrigin origin;
  final String? platform;
  final String? taskType;
  final String? assignedBy;
  final String? followUpNote;

  const CaptureItem({
    required this.id,
    required this.productName,
    required this.category,
    required this.timestamp,
    required this.location,
    required this.syncStatus,
    this.origin = CaptureOrigin.selfCaptured,
    this.platform,
    this.taskType,
    this.assignedBy,
    this.followUpNote,
  });

  bool get isAssignedTask => origin == CaptureOrigin.assignedTask;

  /// Factory helper providing realistic mock captures for previewing
  /// all three sync status chips (Synced, Pending Upload, Failed).
  static List<CaptureItem> mockItems() {
    final now = DateTime.now();
    return [
      CaptureItem(
        id: 'SCAN-2026-0901-01',
        productName: 'Parle-G Glucose Biscuits 100g',
        category: 'Rigid Paperboard Box',
        timestamp: now.subtract(const Duration(minutes: 18)),
        location: 'Sri Murugan Provisions, Gandhipuram',
        syncStatus: SyncStatus.synced,
        origin: CaptureOrigin.selfCaptured,
      ),
      CaptureItem(
        id: 'SCAN-2026-0901-02',
        productName: 'Amul Pasteurised Butter 500g',
        category: 'Paperboard Outer Carton',
        timestamp: now.subtract(const Duration(minutes: 42)),
        location: 'Heritage Mart, RS Puram',
        syncStatus: SyncStatus.pendingUpload,
        origin: CaptureOrigin.selfCaptured,
      ),
      CaptureItem(
        id: 'SCAN-2026-0901-03',
        productName: 'Maggi 2-Minute Noodles 70g',
        category: 'Flexible Poly Wrapper',
        timestamp: now.subtract(const Duration(hours: 1, minutes: 15)),
        location: 'Nilgiris Supermarket, Peelamedu',
        syncStatus: SyncStatus.failed,
        origin: CaptureOrigin.selfCaptured,
      ),
    ];
  }

  /// Mock assigned follow-up tasks from senior LMO per §5.3
  static List<CaptureItem> mockAssignedTasks() {
    final now = DateTime.now();
    return [
      CaptureItem(
        id: 'SCAN-ECOM-BLK01',
        productName: 'Fortune Sunlite Refined Sunflower Oil 1L',
        category: 'E-Commerce Packaging Follow-up',
        timestamp: now.subtract(const Duration(hours: 2, minutes: 10)),
        location: 'Blinkit Dark Store #42, Madurai Central',
        syncStatus: SyncStatus.synced,
        origin: CaptureOrigin.assignedTask,
        platform: 'Blinkit',
        taskType: 'field_followup',
        assignedBy: 'Senior LMO Priya Sharma',
        followUpNote:
            'Rule 6(1)(e) Net Qty Font Violation (1.2mm < 3.0mm mandated). Physical stock verification & Section 39 notice required.',
      ),
    ];
  }
}
