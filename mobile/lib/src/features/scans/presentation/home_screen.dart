import 'package:flutter/material.dart';
import '../../../core/database/database_helper.dart';
import '../../../core/theme/design_tokens.dart';
import '../../../core/widgets/calibration_tick_rule.dart';
import '../../../core/widgets/status_chip.dart';
import '../../auth/data/auth_service.dart';
import '../../auth/presentation/login_screen.dart';
import '../../capture/presentation/capture_screen.dart';
import '../../notifications/presentation/notifications_screen.dart';
import '../../notifications/services/event_polling_service.dart';
import '../../notifications/services/local_notification_service.dart';
import '../../notifications/services/notification_service.dart';
import '../../settings/presentation/settings_screen.dart';
import '../models/capture_item.dart';
import '../models/capture_record.dart';
import '../services/assigned_tasks_service.dart';
import '../services/sync_worker.dart';
import '../services/verdict_sync_service.dart';
import 'scan_detail_screen.dart';
import 'sync_queue_screen.dart';
import '../../../core/utils/short_id.dart';
import 'widgets/capture_card.dart';
import 'widgets/metric_card.dart';

enum HomeTabFilter { all, myCaptures, assignedToMe }

/// Home / Today's Scans Screen (Mobile UX §2, Screen 2)
///
/// Landing screen after LMO login.
/// Lists today's captures with sync status chips (Synced / Pending Upload / Failed).
/// Features big bottom-anchored "New Scan" primary button.
class HomeScreen extends StatefulWidget {
  final List<CaptureItem>? initialCaptures;

  const HomeScreen({
    super.key,
    this.initialCaptures,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  late List<CaptureItem> _captures;
  late final SyncWorker _syncWorker;
  late final NotificationService _notificationService;
  late final AssignedTasksService _assignedTasksService;
  late final EventPollingService _eventPolling;
  late final VerdictSyncService _verdictSync;
  HomeTabFilter _activeFilter = HomeTabFilter.all;
  int _stuckCount = 0;

  /// True when this screen owns the live services. A test that supplies
  /// [HomeScreen.initialCaptures] is exercising layout, not the network, so it
  /// gets no timers.
  bool get _isLive => widget.initialCaptures == null;

  @override
  void initState() {
    super.initState();
    _captures = widget.initialCaptures ?? [];
    _syncWorker = SyncWorker();
    _syncWorker.addListener(_onSyncWorkerUpdate);
    _notificationService = NotificationService();
    _notificationService.addListener(_onNotificationUpdate);
    _assignedTasksService = AssignedTasksService();
    _assignedTasksService.addListener(_onAssignedTasksUpdate);
    _eventPolling = EventPollingService();
    _verdictSync = VerdictSyncService();
    _verdictSync.addListener(_onVerdictUpdate);

    // Request Android 13+ runtime POST_NOTIFICATIONS permission
    LocalNotificationService().requestPermissions();

    if (_isLive) {
      WidgetsBinding.instance.addObserver(this);
      _loadCapturesFromDb();
      _assignedTasksService.loadLocalTasks();
      _assignedTasksService.syncRemoteTasks();
      // Verdicts and dashboard events only reach the officer if something
      // asks for them; nothing pushed to this app before.
      _eventPolling.startPolling();
      _verdictSync.start();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!_isLive) return;
    if (state == AppLifecycleState.resumed) {
      _eventPolling.startPolling();
      _verdictSync.start();
      _loadCapturesFromDb();
    } else if (state == AppLifecycleState.paused || state == AppLifecycleState.detached) {
      // WorkManager covers the background case; foreground timers would only
      // drain the battery.
      _eventPolling.stopPolling();
      _verdictSync.stop();
    }
  }

  void _onVerdictUpdate() {
    if (mounted) _loadCapturesFromDb();
  }

  @override
  void dispose() {
    _syncWorker.removeListener(_onSyncWorkerUpdate);
    _notificationService.removeListener(_onNotificationUpdate);
    _assignedTasksService.removeListener(_onAssignedTasksUpdate);
    _verdictSync.removeListener(_onVerdictUpdate);
    if (_isLive) {
      WidgetsBinding.instance.removeObserver(this);
      _eventPolling.stopPolling();
      _verdictSync.stop();
    }
    super.dispose();
  }

  void _onAssignedTasksUpdate() {
    if (mounted) setState(() {});
  }

  void _onNotificationUpdate() {
    if (mounted) setState(() {});
  }

  void _onSyncWorkerUpdate() {
    if (_isLive && mounted) {
      _loadCapturesFromDb();
    }
  }


  Future<void> _loadCapturesFromDb() async {
    try {
      final records = await DatabaseHelper().getAllCaptures();
      if (!mounted) return;

      final stuck = records.where((r) => r.retryCount > 10).length;

      setState(() {
        _captures = records.map((r) => _recordToItem(r)).toList();
        _stuckCount = stuck;
      });
    } catch (e) {
      debugPrint('Error loading captures from SQLite: $e');
    }
  }

  void _openSyncQueue() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const SyncQueueScreen(),
      ),
    ).then((_) => _loadCapturesFromDb());
  }

  void _openNotifications() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const NotificationsScreen(),
      ),
    );
  }

  CaptureItem _recordToItem(CaptureRecord r) {
    DateTime parsedTime;
    try {
      parsedTime = DateTime.parse(r.capturedAtUtc).toLocal();
    } catch (_) {
      parsedTime = DateTime.now();
    }

    final idDisplay = r.serverScanId != null && r.serverScanId!.isNotEmpty
        ? 'SCAN-${shortId(r.serverScanId)}'
        : 'LOC-${shortId(r.localId)}';

    final locationDisplay = r.lat != null && r.lng != null
        ? 'GPS: ${r.lat!.toStringAsFixed(4)}, ${r.lng!.toStringAsFixed(4)}'
        : 'Active Field Inspection Site';

    final shape = r.productType.isEmpty
        ? 'Package'
        : '${r.productType[0].toUpperCase()}${r.productType.substring(1)}';

    return CaptureItem(
      id: idDisplay,
      localId: r.localId,
      productName: (r.productName != null && r.productName!.trim().isNotEmpty)
          ? r.productName!.trim()
          : 'Unnamed package',
      category: '$shape - measured against ${r.referenceObjectType.replaceAll('_', ' ')}',
      timestamp: parsedTime,
      location: locationDisplay,
      syncStatus: r.toUiSyncStatus,
      verdict: r.verdict,
    );
  }

  List<CaptureItem> get _allItems {
    if (widget.initialCaptures != null) {
      return _captures;
    }
    return [..._captures, ..._assignedTasksService.assignedItems];
  }

  void _openSettings() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const SettingsScreen()),
    );
  }

  List<CaptureItem> get _displayedItems {
    final all = _allItems;
    switch (_activeFilter) {
      case HomeTabFilter.myCaptures:
        return all.where((c) => !c.isAssignedTask).toList();
      case HomeTabFilter.assignedToMe:
        return all.where((c) => c.isAssignedTask).toList();
      case HomeTabFilter.all:
        return all;
    }
  }

  /// Own captures open the verdict screen; assigned tasks have no local row,
  /// so they keep the summary sheet.
  void _openCapture(CaptureItem item) {
    final localId = item.localId;
    if (localId == null) {
      _showItemDetails(item);
      return;
    }
    Navigator.of(context)
        .push(
          MaterialPageRoute(builder: (_) => ScanDetailScreen(localId: localId)),
        )
        .then((_) {
      if (_isLive && mounted) _loadCapturesFromDb();
    });
  }

  void _showItemDetails(CaptureItem item) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.paper000,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.space3),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      item.isAssignedTask
                          ? 'Assigned task details'
                          : 'Field Capture Details',
                      style: AppTypography.base.copyWith(fontWeight: FontWeight.bold),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 20),
                      onPressed: () => Navigator.of(context).pop(),
                    ),
                  ],
                ),
                const Divider(),
                const SizedBox(height: AppSpacing.space1),
                Text(item.productName, style: AppTypography.base.copyWith(fontWeight: FontWeight.w600)),
                Text(item.category, style: AppTypography.xs.copyWith(color: AppColors.ink600)),
                const SizedBox(height: AppSpacing.space2),
                if (item.isAssignedTask && item.followUpNote != null) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(AppSpacing.space2),
                    decoration: BoxDecoration(
                      color: AppColors.paper100,
                      borderRadius: BorderRadius.circular(AppRadius.card),
                      border: Border.all(color: AppColors.verdictPending.withValues(alpha: 0.4)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'INSPECTION INSTRUCTIONS',
                          style: AppTypography.xs.copyWith(
                            fontWeight: FontWeight.bold,
                            color: AppColors.verdictPending,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.space05),
                        Text(item.followUpNote!, style: AppTypography.xs),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.space2),
                ],
                ElevatedButton.icon(
                  onPressed: () {
                    Navigator.of(context).pop();
                    _handleNewScan();
                  },
                  icon: const Icon(Icons.camera_alt, color: AppColors.paper000),
                  label: Text(item.isAssignedTask ? 'START ON-SITE INSPECTION' : 'RE-SCAN ITEM'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _handleLogout() async {
    await AuthService().logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => const LoginScreen(),
      ),
    );
  }

  Future<void> _handleNewScan() async {
    await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(
        builder: (_) => const CaptureScreen(),
      ),
    );

    if (mounted) {
      _loadCapturesFromDb();
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = AuthService().currentUser;
    final officerName = user?.fullName.isNotEmpty == true ? user!.fullName : 'Field Officer';
    final district = user?.district?.isNotEmpty == true ? user!.district! : 'Jurisdiction';

    final all = _allItems;
    final displayed = _displayedItems;

    final myCapturesCount = all.where((c) => !c.isAssignedTask).length;
    final assignedCount = all.where((c) => c.isAssignedTask).length;

    final syncedCount = displayed.where((c) => c.syncStatus == SyncStatus.synced).length;
    final pendingCount = displayed.where((c) => c.syncStatus == SyncStatus.pendingUpload).length;
    final failedCount = displayed.where((c) => c.syncStatus == SyncStatus.failed).length;

    return Scaffold(
      backgroundColor: AppColors.paper100,
      appBar: AppBar(
        title: const Text('MetrologyAI — Field LMO'),
        actions: [
          IconButton(
            tooltip: 'Sync Queue',
            icon: const Icon(Icons.cloud_sync_outlined, color: AppColors.paper000),
            onPressed: _openSyncQueue,
          ),
          IconButton(
            tooltip: 'Notifications',
            icon: Badge(
              isLabelVisible: _notificationService.unreadCount > 0,
              label: Text('${_notificationService.unreadCount}'),
              child: const Icon(Icons.notifications_outlined, color: AppColors.paper000),
            ),
            onPressed: _openNotifications,
          ),
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout, color: AppColors.paper000),
            onPressed: _handleLogout,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Scrollable Content
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
                children: [
                  // Stuck Captures Alert Banner (§3.1: notify_user("photo stuck, check manually"))
                  if (_stuckCount > 0) ...[
                    InkWell(
                      onTap: _openSyncQueue,
                      borderRadius: BorderRadius.circular(AppRadius.card),
                      child: Container(
                        padding: const EdgeInsets.all(AppSpacing.space2),
                        decoration: BoxDecoration(
                          color: AppColors.paper000,
                          borderRadius: BorderRadius.circular(AppRadius.card),
                          border: Border.all(color: AppColors.verdictPending, width: 1.5),
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.warning_amber_rounded,
                              color: AppColors.verdictPending,
                              size: 22.0,
                            ),
                            const SizedBox(width: AppSpacing.space1),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'STUCK CAPTURES ALERT ($_stuckCount)',
                                    style: AppTypography.xs.copyWith(
                                      color: AppColors.verdictPending,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    '$_stuckCount capture(s) exceeded 10 upload attempts. Tap to inspect & retry manually.',
                                    style: AppTypography.xs.copyWith(color: AppColors.ink900),
                                  ),
                                ],
                              ),
                            ),
                            const Icon(Icons.arrow_forward_ios, size: 12.0, color: AppColors.ink600),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.space2),
                  ],

                  // Officer Identity & Status Card
                  Card(
                    margin: EdgeInsets.zero,
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.space2),
                      child: Row(
                        children: [
                          Container(
                            width: 40.0,
                            height: 40.0,
                            decoration: BoxDecoration(
                              color: AppColors.ink900,
                              borderRadius: BorderRadius.circular(AppRadius.card),
                            ),
                            child: const Icon(
                              Icons.verified_user,
                              color: AppColors.brass500,
                              size: 22.0,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.space2),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  officerName,
                                  style: AppTypography.base.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: AppColors.ink900,
                                  ),
                                ),
                                const SizedBox(height: AppSpacing.space05),
                                Text(
                                  'District: $district • PCR 2011 Active',
                                  style: AppTypography.xs.copyWith(
                                    color: AppColors.ink600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: 'Profile & settings',
                            onPressed: _openSettings,
                            icon: const Icon(Icons.settings_outlined, color: AppColors.ink600),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // Signature Calibration Tick Rule divider
                  const CalibrationTickRule(),

                  // Today's Scans Header & Metric Summary
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            "Today's Scans",
                            style: AppTypography.lg,
                          ),
                          const SizedBox(height: AppSpacing.space05),
                          Text(
                            'Field capture log & synchronisation state',
                            style: AppTypography.xs.copyWith(color: AppColors.ink600),
                          ),
                        ],
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.space1,
                          vertical: AppSpacing.space05,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.paper000,
                          borderRadius: BorderRadius.circular(AppRadius.card),
                          border: Border.all(
                            color: AppColors.ink600.withValues(alpha: 0.3),
                            width: 1.0,
                          ),
                        ),
                        child: Text(
                          'TOTAL: ${displayed.length}',
                          style: AppTypography.dataMono.copyWith(
                            fontSize: 12.0,
                            fontWeight: FontWeight.bold,
                            color: AppColors.ink900,
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: AppSpacing.space2),

                  // Metrics Chips
                  Row(
                    children: [
                      Expanded(
                        child: MetricCard(
                          label: 'Synced',
                          count: syncedCount,
                          color: AppColors.verdictPass,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.space1),
                      Expanded(
                        child: MetricCard(
                          label: 'Pending',
                          count: pendingCount,
                          color: AppColors.verdictPending,
                          onTap: _openSyncQueue,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.space1),
                      Expanded(
                        child: MetricCard(
                          label: 'Failed',
                          count: failedCount,
                          color: AppColors.verdictFail,
                          onTap: _openSyncQueue,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: AppSpacing.space2),

                  // Filter Segment Tabs (§5.3: My Captures vs Assigned to Me)
                  _buildFilterTabs(
                    allCount: all.length,
                    myCount: myCapturesCount,
                    assignedCount: assignedCount,
                  ),

                  const SizedBox(height: AppSpacing.space2),

                  // Captures List or Empty State
                  if (displayed.isEmpty) ...[
                    _buildEmptyState(),
                  ] else ...[
                    ...displayed.map(
                      (capture) => CaptureCard(
                        capture: capture,
                        onTap: () => _openCapture(capture),
                      ),
                    ),
                  ],

                  const SizedBox(height: AppSpacing.space2),
                ],
              ),
            ),

            // Bottom Anchored Primary Action Container
            // Per §8: 48px minimum touch target, bottom-anchored within thumb reach
            Container(
              padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
              decoration: BoxDecoration(
                color: AppColors.paper000,
                border: Border(
                  top: BorderSide(
                    color: AppColors.ink600.withValues(alpha: 0.2),
                    width: 1.0,
                  ),
                ),
              ),
              child: ElevatedButton.icon(
                onPressed: _handleNewScan,
                icon: const Icon(Icons.camera_alt, color: AppColors.paper000),
                label: const Text('NEW SCAN (AR GUIDE)'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.space4),
      decoration: BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(
          color: AppColors.ink600.withValues(alpha: 0.2),
          width: 1.0,
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 56.0,
            height: 56.0,
            decoration: BoxDecoration(
              color: AppColors.paper100,
              borderRadius: BorderRadius.circular(AppRadius.card),
            ),
            child: const Icon(
              Icons.document_scanner_outlined,
              color: AppColors.ink600,
              size: 30.0,
            ),
          ),
          const SizedBox(height: AppSpacing.space2),
          const Text(
            'No Captures Recorded Today',
            style: AppTypography.lg,
          ),
          const SizedBox(height: AppSpacing.space1),
          Text(
            'Evidence capture log is empty. Use the button below to initiate compliance capture with reference card calibration.',
            textAlign: TextAlign.center,
            style: AppTypography.xs.copyWith(color: AppColors.ink600),
          ),
          const SizedBox(height: AppSpacing.space2),
          Text(
            'Tap New Scan to record your first inspection of the day.',
            style: AppTypography.dataMono.copyWith(
              fontSize: 12.0,
              color: AppColors.brass500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterTabs({
    required int allCount,
    required int myCount,
    required int assignedCount,
  }) {
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.ink600.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          _buildFilterPill(
            label: 'All',
            filter: HomeTabFilter.all,
            count: allCount,
          ),
          _buildFilterPill(
            label: 'My Captures',
            filter: HomeTabFilter.myCaptures,
            count: myCount,
          ),
          _buildFilterPill(
            label: 'Assigned to Me',
            filter: HomeTabFilter.assignedToMe,
            count: assignedCount,
            isHighlight: assignedCount > 0,
          ),
        ],
      ),
    );
  }

  Widget _buildFilterPill({
    required String label,
    required HomeTabFilter filter,
    required int count,
    bool isHighlight = false,
  }) {
    final isSelected = _activeFilter == filter;
    return Expanded(
      child: InkWell(
        onTap: () {
          setState(() {
            _activeFilter = filter;
          });
        },
        borderRadius: BorderRadius.circular(AppRadius.card - 2),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.ink900 : Colors.transparent,
            borderRadius: BorderRadius.circular(AppRadius.card - 2),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.xs.copyWith(
                    color: isSelected
                        ? AppColors.paper000
                        : (isHighlight ? AppColors.verdictPending : AppColors.ink900),
                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                    fontSize: 11,
                  ),
                ),
              ),
              const SizedBox(width: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: isSelected
                      ? AppColors.brass500
                      : AppColors.ink600.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$count',
                  style: AppTypography.dataMono.copyWith(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: isSelected ? AppColors.ink900 : AppColors.ink900,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Metric Counter Card
