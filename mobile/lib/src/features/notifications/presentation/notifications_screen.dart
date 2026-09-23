import 'package:flutter/material.dart';
import '../../../core/theme/design_tokens.dart';
import '../../../core/widgets/calibration_tick_rule.dart';
import '../../../core/database/database_helper.dart';
import '../../scans/models/capture_record.dart';
import '../../scans/presentation/scan_detail_screen.dart';
import '../../scans/presentation/sync_queue_screen.dart';
import '../models/notification_item.dart';

/// Notifications Screen (Mobile UX §2, Screen 7)
///
/// Pushed updates and field officer alerts for compliance verdicts,
import '../services/notification_service.dart';

/// Notifications Screen (Mobile UX §2, Screen 7)
///
/// Pushed updates and field officer alerts for compliance verdicts,
/// queue sync completions, stuck photo warnings, and legal notices.
class NotificationsScreen extends StatefulWidget {
  final List<NotificationItem>? initialNotifications;
  final NotificationService? notificationService;

  const NotificationsScreen({
    super.key,
    this.initialNotifications,
    this.notificationService,
  });

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  late final NotificationService _notificationService;
  List<NotificationItem>? _localNotifications;
  String _selectedFilter = 'All';

  @override
  void initState() {
    super.initState();
    _notificationService = widget.notificationService ?? NotificationService();
    if (widget.initialNotifications != null) {
      _localNotifications = List<NotificationItem>.from(widget.initialNotifications!);
    } else {
      _notificationService.addListener(_onNotificationsChanged);
    }
  }

  @override
  void dispose() {
    if (widget.initialNotifications == null) {
      _notificationService.removeListener(_onNotificationsChanged);
    }
    super.dispose();
  }

  void _onNotificationsChanged() {
    if (mounted) setState(() {});
  }

  List<NotificationItem> get _notifications =>
      _localNotifications ?? _notificationService.notifications;

  List<NotificationItem> get _filteredNotifications {
    final list = _notifications;
    if (_selectedFilter == 'All') return list;
    if (_selectedFilter == 'Compliance') {
      return list.where((n) => n.category == NotificationCategory.compliance).toList();
    }
    if (_selectedFilter == 'Sync & Queue') {
      return list
          .where((n) =>
              n.category == NotificationCategory.syncEvent ||
              n.category == NotificationCategory.stuckAlert)
          .toList();
    }
    if (_selectedFilter == 'Notices') {
      return list
          .where((n) => n.category == NotificationCategory.challanNotice)
          .toList();
    }
    return list;
  }

  void _markAllAsRead() {
    if (_localNotifications != null) {
      setState(() {
        for (final n in _localNotifications!) {
          n.isRead = true;
        }
      });
    } else {
      _notificationService.markAllAsRead();
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        backgroundColor: AppColors.ink900,
        content: Text('All notifications marked as read.'),
        duration: Duration(seconds: 1),
      ),
    );
  }

  Future<void> _handleNotificationTap(NotificationItem item) async {
    if (_localNotifications != null) {
      setState(() {
        item.isRead = true;
      });
    } else {
      await _notificationService.markAsRead(item.id);
    }

    final route = item.deepLinkRoute;
    if (route == null) return;

    if (route == '/sync-queue') {
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const SyncQueueScreen()),
      );
      return;
    }

    if (route.startsWith('/scans/')) {
      // The alert carries the server's scan id; the detail screen reads the
      // local row, so resolve one to the other before navigating.
      final serverScanId = route.substring('/scans/'.length);
      CaptureRecord? capture;
      try {
        capture = await DatabaseHelper().getCaptureByServerScanId(serverScanId);
      } catch (e) {
        debugPrint('[Notifications] Could not resolve deep link $route: $e');
      }

      if (!mounted) return;
      if (capture == null) {
        // The scan belongs to someone else's device, or its local row was
        // discarded. Say so rather than opening an empty screen.
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('This scan is not stored on this device. Open it on the dashboard.'),
          ),
        );
        return;
      }

      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ScanDetailScreen(
            localId: capture!.localId,
            initialRecord: capture,
          ),
        ),
      );
    }
  }


  String _formatTimestamp(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  @override
  Widget build(BuildContext context) {
    final unreadCount = _notifications.where((n) => !n.isRead).length;

    return Scaffold(
      backgroundColor: AppColors.paper100,
      appBar: AppBar(
        title: const Text('Field Notifications'),
        actions: [
          if (unreadCount > 0)
            TextButton(
              onPressed: _markAllAsRead,
              child: Text(
                'MARK ALL READ',
                style: AppTypography.xs.copyWith(
                  fontWeight: FontWeight.bold,
                  color: AppColors.brass500,
                ),
              ),
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Filter Chips Header
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(
                horizontal: AppConstraints.mobileScreenMargin,
                vertical: AppSpacing.space2,
              ),
              child: Row(
                children: [
                  _buildFilterChip('All'),
                  const SizedBox(width: AppSpacing.space1),
                  _buildFilterChip('Compliance'),
                  const SizedBox(width: AppSpacing.space1),
                  _buildFilterChip('Sync & Queue'),
                  const SizedBox(width: AppSpacing.space1),
                  _buildFilterChip('Notices'),
                ],
              ),
            ),

            // Divider
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: AppConstraints.mobileScreenMargin),
              child: CalibrationTickRule(),
            ),

            // Notification List Area
            Expanded(
              child: _filteredNotifications.isEmpty
                  ? _buildEmptyState()
                  : ListView.separated(
                      padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
                      itemCount: _filteredNotifications.length,
                      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.space2),
                      itemBuilder: (context, index) {
                        final item = _filteredNotifications[index];
                        return _buildNotificationCard(item);
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String label) {
    final isSelected = _selectedFilter == label;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        if (selected) {
          setState(() {
            _selectedFilter = label;
          });
        }
      },
      selectedColor: AppColors.ink900,
      backgroundColor: AppColors.paper000,
      labelStyle: AppTypography.xs.copyWith(
        color: isSelected ? AppColors.paper000 : AppColors.ink900,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.sealBadge),
        side: BorderSide(
          color: isSelected ? AppColors.ink900 : AppColors.ink600.withValues(alpha: 0.3),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.space4),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 56.0,
              height: 56.0,
              decoration: BoxDecoration(
                color: AppColors.ink900.withValues(alpha: 0.05),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.notifications_none,
                color: AppColors.ink600,
                size: 32.0,
              ),
            ),
            const SizedBox(height: AppSpacing.space2),
            const Text(
              'No Notifications',
              style: AppTypography.lg,
            ),
            const SizedBox(height: AppSpacing.space1),
            Text(
              'You are all caught up on all field inspection events and repository alerts.',
              textAlign: TextAlign.center,
              style: AppTypography.xs.copyWith(color: AppColors.ink600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNotificationCard(NotificationItem item) {
    return InkWell(
      onTap: () => _handleNotificationTap(item),
      borderRadius: BorderRadius.circular(AppRadius.card),
      child: Card(
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
          side: BorderSide(
            color: item.isRead
                ? AppColors.ink600.withValues(alpha: 0.15)
                : AppColors.brass500.withValues(alpha: 0.6),
            width: item.isRead ? 1.0 : 1.5,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.space2),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Category Icon Container
                  Container(
                    width: 34.0,
                    height: 34.0,
                    decoration: BoxDecoration(
                      color: item.category.color.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(AppRadius.card),
                    ),
                    child: Icon(
                      item.category.icon,
                      color: item.category.color,
                      size: 18.0,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.space1),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              item.category.label.toUpperCase(),
                              style: AppTypography.xs.copyWith(
                                color: item.category.color,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 0.6,
                              ),
                            ),
                            Text(
                              _formatTimestamp(item.timestamp),
                              style: AppTypography.dataMono.copyWith(
                                fontSize: 11.0,
                                color: AppColors.ink600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.space05),
                        Text(
                          item.title,
                          style: AppTypography.base.copyWith(
                            fontWeight: item.isRead ? FontWeight.w600 : FontWeight.bold,
                            color: AppColors.ink900,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.space1),
              Padding(
                padding: const EdgeInsets.only(left: 42.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.body,
                      style: AppTypography.xs.copyWith(
                        color: AppColors.ink900,
                        height: 1.4,
                      ),
                    ),
                    if (item.deepLinkRoute != null) ...[
                      const SizedBox(height: AppSpacing.space1),
                      Row(
                        children: [
                          Text(
                            'OPEN SYNC QUEUE',
                            style: AppTypography.xs.copyWith(
                              color: AppColors.brass500,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(
                            Icons.arrow_forward,
                            size: 12.0,
                            color: AppColors.brass500,
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
