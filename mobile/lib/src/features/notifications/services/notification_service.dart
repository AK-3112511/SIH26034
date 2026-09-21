import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/app_event.dart';
import '../models/notification_item.dart';
import 'event_polling_service.dart';
import 'local_notification_service.dart';

/// Central Reactive Notification Coordinator (§5.2 & §6.2)
///
/// Wires `scan.status_changed` and `task.assigned` events directly into:
/// 1. OS-level lock screen notifications via [LocalNotificationService]
/// 2. In-app notifications feed via [NotificationsScreen]
class NotificationService extends ChangeNotifier {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;

  @visibleForTesting
  factory NotificationService.createTestInstance({
    EventPollingService? eventPollingService,
    LocalNotificationService? localNotificationService,
    List<NotificationItem>? initialNotifications,
  }) {
    return NotificationService._internal(
      eventPollingService: eventPollingService,
      localNotificationService: localNotificationService,
      initialNotifications: initialNotifications,
    );
  }

  NotificationService._internal({
    EventPollingService? eventPollingService,
    LocalNotificationService? localNotificationService,
    List<NotificationItem>? initialNotifications,
  })  : _eventPollingService = eventPollingService ?? EventPollingService(),
        _localNotificationService = localNotificationService ?? LocalNotificationService(),
        _notifications = initialNotifications ?? NotificationItem.mockNotifications() {
    _initEventSubscription();
  }

  final EventPollingService _eventPollingService;
  final LocalNotificationService _localNotificationService;
  StreamSubscription<AppEvent>? _eventSubscription;
  final List<NotificationItem> _notifications;

  List<NotificationItem> get notifications => List.unmodifiable(_notifications);
  int get unreadCount => _notifications.where((n) => !n.isRead).length;

  void _initEventSubscription() {
    _eventSubscription = _eventPollingService.eventStream.listen((event) {
      handleEvent(event);
    });
  }

  /// Process an incoming AppEvent (can be called from foreground stream or headless WorkManager)
  Future<void> handleEvent(AppEvent event) async {
    if (event.isScanStatusChanged) {
      final payload = event.scanStatusChangedPayload;
      if (payload == null) return;

      final isFailed = payload.newStatus.toUpperCase() == 'FAILED' ||
          payload.newStatus.toUpperCase() == 'FAIL';
      final isPassed = payload.newStatus.toUpperCase() == 'PASSED' ||
          payload.newStatus.toUpperCase() == 'PASS';

      final title = isFailed
          ? 'Compliance Verdict: Failed'
          : isPassed
              ? 'Compliance Verdict: Passed'
              : 'Scan Status: ${payload.newStatus}';

      final shortId = payload.scanId.length > 8
          ? payload.scanId.substring(0, 8).toUpperCase()
          : payload.scanId.toUpperCase();

      String body;
      if (isFailed) {
        final failedRules = payload.ruleResults
            .where((r) => r['status']?.toString().toUpperCase() == 'FAIL')
            .toList();

        final ruleSummary = failedRules.isNotEmpty
            ? ' — Rule ${failedRules.map((r) => r['rule_id']).join(', ')}'
            : '';

        final reasonSummary = failedRules.isNotEmpty && failedRules[0]['reason'] != null
            ? ' (${failedRules[0]['reason']})'
            : '';

        // Exact §5.2 prompt requirement:
        // "A field LMO gets notified when their own scan's verdict is confirmed/overridden by a senior LMO"
        body =
            'Your scan #$shortId confirmed FAILED$ruleSummary$reasonSummary. Re-inspection or store follow-up required (§5.2).';
      } else if (isPassed) {
        body =
            'Your scan #$shortId confirmed PASSED. All statutory Legal Metrology declarations verified.';
      } else {
        body = 'Your scan #$shortId status updated to ${payload.newStatus}.';
      }

      final item = NotificationItem(
        id: 'notif-${payload.scanId}-${DateTime.now().millisecondsSinceEpoch}',
        title: title,
        body: body,
        category: NotificationCategory.compliance,
        timestamp: event.createdAt,
        isRead: false,
        deepLinkRoute: '/scans/${payload.scanId}',
      );

      _notifications.insert(0, item);
      notifyListeners();

      // Trigger OS-level notification on lock screen and notification tray
      await _localNotificationService.showComplianceNotification(
        title: title,
        body: body,
        payload: payload.scanId,
      );
    } else if (event.isTaskAssigned) {
      final payload = event.taskAssignedPayload;
      if (payload == null) return;

      final shortId = payload.scanId.length > 8
          ? payload.scanId.substring(0, 8).toUpperCase()
          : payload.scanId.toUpperCase();

      const title = 'New Task: Field Follow-up';
      final body =
          'Scan #$shortId assigned to you for field verification (§5.3). Check Home screen.';

      final item = NotificationItem(
        id: 'task-${payload.scanId}-${DateTime.now().millisecondsSinceEpoch}',
        title: title,
        body: body,
        category: NotificationCategory.syncEvent,
        timestamp: event.createdAt,
        isRead: false,
        deepLinkRoute: '/scans/${payload.scanId}',
      );

      _notifications.insert(0, item);
      notifyListeners();

      await _localNotificationService.showComplianceNotification(
        title: title,
        body: body,
        payload: payload.scanId,
      );
    }
  }

  void markAllAsRead() {
    for (final n in _notifications) {
      n.isRead = true;
    }
    notifyListeners();
  }

  void markAsRead(String id) {
    for (final n in _notifications) {
      if (n.id == id) {
        n.isRead = true;
        break;
      }
    }
    notifyListeners();
  }

  void addNotification(NotificationItem item) {
    _notifications.insert(0, item);
    notifyListeners();
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    super.dispose();
  }
}
