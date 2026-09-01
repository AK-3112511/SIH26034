import '../../../core/widgets/status_chip.dart';

/// Representation of a captured package inspection item
/// Used on the Home Screen (§2, Screen 2) and offline sync queue.
class CaptureItem {
  final String id;
  final String productName;
  final String category;
  final DateTime timestamp;
  final String location;
  final SyncStatus syncStatus;

  const CaptureItem({
    required this.id,
    required this.productName,
    required this.category,
    required this.timestamp,
    required this.location,
    required this.syncStatus,
  });

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
      ),
      CaptureItem(
        id: 'SCAN-2026-0901-02',
        productName: 'Amul Pasteurised Butter 500g',
        category: 'Paperboard Outer Carton',
        timestamp: now.subtract(const Duration(minutes: 42)),
        location: 'Heritage Mart, RS Puram',
        syncStatus: SyncStatus.pendingUpload,
      ),
      CaptureItem(
        id: 'SCAN-2026-0901-03',
        productName: 'Maggi 2-Minute Noodles 70g',
        category: 'Flexible Poly Wrapper',
        timestamp: now.subtract(const Duration(hours: 1, minutes: 15)),
        location: 'Nilgiris Supermarket, Peelamedu',
        syncStatus: SyncStatus.failed,
      ),
    ];
  }
}
