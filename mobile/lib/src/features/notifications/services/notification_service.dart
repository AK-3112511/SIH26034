import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../../core/database/database_helper.dart';
import '../models/app_event.dart';
import '../models/notification_item.dart';
import 'event_polling_service.dart';
import 'local_notification_service.dart';
import '../../../core/utils/short_id.dart';

/// Central Reactive Notification Coordinator
///
/// Wires `scan.status_changed` and `task.assigned` events into:
/// 1. OS-level lock screen notifications via [LocalNotificationService]
/// 2. The in-app feed, persisted in SQLite so alerts raised by the headless
///    background isolate are still there next time the app opens.
class NotificationService extends ChangeNotifier {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;

  @visibleForTesting
  factory NotificationService.createTestInstance({
    EventPollingService? eventPollingService,
    LocalNotificationService? localNotificationService,
    DatabaseHelper? dbHelper,
    List<NotificationItem>? initialNotifications,
  }) {
    return NotificationService._internal(
      eventPollingService: eventPollingService,
      localNotificationService: localNotificationService,
      dbHelper: dbHelper,
      initialNotifications: initialNotifications,
    );
  }

  NotificationService._internal({
    EventPollingService? eventPollingService,
    LocalNotificationService? localNotificationService,
    DatabaseHelper? dbHelper,
    List<NotificationItem>? initialNotifications,
  })  : _eventPollingService = eventPollingService ?? EventPollingService(),
        _localNotificationService = localNotificationService ?? LocalNotificationService(),
        _dbHelper = dbHelper ?? DatabaseHelper(),
        _notifications = List<NotificationItem>.from(initialNotifications ?? const []) {
    _initEventSubscription();
  }

  final EventPollingService _eventPollingService;
  final LocalNotificationService _localNotificationService;
  final DatabaseHelper _dbHelper;
  StreamSubscription<AppEvent>? _eventSubscription;
  final List<NotificationItem> _notifications;

  List<NotificationItem> get notifications => List.unmodifiable(_notifications);
  int get unreadCount => _notifications.where((n) => !n.isRead).length;

  void _initEventSubscription() {
    _eventSubscription = _eventPollingService.eventStream.listen((event) {
      handleEvent(event);
    });
  }

  /// Load the stored feed. Called once at app start.
  Future<void> loadPersisted() async {
    try {
      final stored = await _dbHelper.getNotifications();
      _notifications
        ..clear()
        ..addAll(stored);
      notifyListeners();
    } catch (e) {
      debugPrint('[NotificationService] Could not load stored notifications: $e');
    }
  }

  /// Process an incoming AppEvent. Safe to call from the foreground stream or
  /// the headless WorkManager isolate.
  Future<void> handleEvent(AppEvent event) async {
    if (event.isScanStatusChanged) {
      final payload = event.scanStatusChangedPayload;
      if (payload == null) return;

      final normalised = payload.newStatus.toUpperCase();
      final isFailed = normalised == 'FAILED' || normalised == 'FAIL';
      final isPassed = normalised == 'PASSED' || normalised == 'PASS';

      final title = isFailed
          ? 'Compliance Verdict: Failed'
          : isPassed
              ? 'Compliance Verdict: Passed'
              : 'Scan Status: ${payload.newStatus}';

      final displayId = shortId(payload.scanId);

      String body;
      if (isFailed) {
        final failedRules = payload.ruleResults
            .where((r) => r['status']?.toString().toUpperCase() == 'FAIL')
            .toList();

        final ruleSummary = failedRules.isNotEmpty
            ? ' - Rule ${failedRules.map((r) => r['rule_id']).join(', ')}'
            : '';

        final reasonSummary = failedRules.isNotEmpty && failedRules[0]['reason'] != null
            ? ' (${failedRules[0]['reason']})'
            : '';

        body = 'Your scan #$displayId was confirmed FAILED$ruleSummary$reasonSummary. '
            'Re-inspection or store follow-up required.';
      } else if (isPassed) {
        body = 'Your scan #$displayId was confirmed PASSED. '
            'All statutory Legal Metrology declarations verified.';
      } else {
        body = 'Your scan #$displayId status updated to ${payload.newStatus}.';
      }

      await _record(
        NotificationItem(
          // Deterministic id: the foreground poller and the background isolate
          // can both see the same event, and must not file it twice.
          id: 'scan-${payload.scanId}-$normalised',
          title: title,
          body: body,
          category: NotificationCategory.compliance,
          timestamp: event.createdAt,
          isRead: false,
          deepLinkRoute: '/scans/${payload.scanId}',
        ),
      );
    } else if (event.isTaskAssigned) {
      final payload = event.taskAssignedPayload;
      if (payload == null) return;

      const title = 'New Task: Field Follow-up';
      final body = 'Scan #${shortId(payload.scanId)} was assigned to you for field '
          'verification. Open the Assigned tab on Home.';

      await _record(
        NotificationItem(
          id: 'task-${payload.scanId}',
          title: title,
          body: body,
          category: NotificationCategory.syncEvent,
          timestamp: event.createdAt,
          isRead: false,
          deepLinkRoute: '/scans/${payload.scanId}',
        ),
      );
    }
  }

  Future<void> _record(NotificationItem item) async {
    final existing = _notifications.indexWhere((n) => n.id == item.id);
    if (existing >= 0) {
      _notifications[existing] = item;
    } else {
      _notifications.insert(0, item);
    }
    notifyListeners();

    // Persistence is durability, not correctness: the feed is already updated,
    // and a slow or unavailable store must not delay the alert an officer is
    // waiting on. Deliberately not awaited.
    unawaited(
      _dbHelper.insertNotification(item).catchError(
        (Object e) => debugPrint('[NotificationService] Could not persist notification: $e'),
      ),
    );

    // Only alert the lock screen for something the officer has not seen.
    if (existing < 0) {
      await _localNotificationService.showComplianceNotification(
        title: item.title,
        body: item.body,
        payload: item.deepLinkRoute,
      );
    }
  }

  Future<void> markAllAsRead() async {
    for (final n in _notifications) {
      n.isRead = true;
    }
    notifyListeners();
    unawaited(
      _dbHelper.markAllNotificationsRead().catchError(
        (Object e) => debugPrint('[NotificationService] Could not persist read state: $e'),
      ),
    );
  }

  Future<void> markAsRead(String id) async {
    for (final n in _notifications) {
      if (n.id == id) {
        n.isRead = true;
        break;
      }
    }
    notifyListeners();
    unawaited(
      _dbHelper.markNotificationRead(id).catchError(
        (Object e) => debugPrint('[NotificationService] Could not persist read state: $e'),
      ),
    );
  }

  Future<void> addNotification(NotificationItem item) => _record(item);

  @override
  void dispose() {
    _eventSubscription?.cancel();
    super.dispose();
  }
}
