import 'package:flutter/material.dart';
import '../../../core/theme/design_tokens.dart';
import '../../../core/widgets/calibration_tick_rule.dart';
import '../../scans/presentation/sync_queue_screen.dart';
import '../models/notification_item.dart';

/// Notifications Screen (Mobile UX §2, Screen 7)
///
/// Pushed updates and field officer alerts for compliance verdicts,
/// queue sync completions, stuck photo warnings, and legal notices.
class NotificationsScreen extends StatefulWidget {
  final List<NotificationItem>? initialNotifications;

  const NotificationsScreen({
    super.key,
    this.initialNotifications,
  });

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  late List<NotificationItem> _notifications;
  String _selectedFilter = 'All';

  @override
  void initState() {
    super.initState();
    _notifications = widget.initialNotifications ?? NotificationItem.mockNotifications();
  }

  List<NotificationItem> get _filteredNotifications {
    if (_selectedFilter == 'All') return _notifications;
    if (_selectedFilter == 'Compliance') {
      return _notifications.where((n) => n.category == NotificationCategory.compliance).toList();
    }
    if (_selectedFilter == 'Sync & Queue') {
      return _notifications
          .where((n) =>
              n.category == NotificationCategory.syncEvent ||
              n.category == NotificationCategory.stuckAlert)
          .toList();
    }
    if (_selectedFilter == 'Notices') {
      return _notifications
          .where((n) => n.category == NotificationCategory.challanNotice)
          .toList();
    }
    return _notifications;
  }

  void _markAllAsRead() {
    setState(() {
      for (final n in _notifications) {
        n.isRead = true;
      }
    });

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        backgroundColor: AppColors.ink900,
        content: Text('All notifications marked as read.'),
        duration: Duration(seconds: 1),
      ),
    );
  }

  void _handleNotificationTap(NotificationItem item) {
    setState(() {
      item.isRead = true;
    });

    if (item.deepLinkRoute == '/sync-queue') {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => const SyncQueueScreen(),
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
