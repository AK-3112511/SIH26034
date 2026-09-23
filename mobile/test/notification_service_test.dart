import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/features/notifications/models/app_event.dart';
import 'package:mobile/src/features/notifications/models/notification_item.dart';
import 'package:mobile/src/features/notifications/services/local_notification_service.dart';
import 'package:mobile/src/features/notifications/services/notification_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Phase 7.2 NotificationService (§5.2 Push Notification Wiring)', () {
    late NotificationService service;

    setUp(() {
      service = NotificationService.createTestInstance(
        initialNotifications: [],
        localNotificationService: LocalNotificationService.createTestInstance(),
      );
    });

    test('Wires scan.status_changed FAILED event into §5.2 notification format', () async {
      final event = AppEvent(
        id: 'evt-001',
        eventType: 'scan.status_changed',
        payload: {
          'scan_id': '4c8e7456-9b1b-4f8a-a123-abcdef123456',
          'new_status': 'FAILED',
          'rule_results': [
            {
              'rule_id': '6(1)(e)',
              'status': 'FAIL',
              'reason': 'Net Qty Font Violation (1.2mm < 3.0mm mandated)',
            }
          ],
          'assigned_lmo_id': 'field-officer-01',
        },
        createdAt: DateTime.now(),
      );

      await service.handleEvent(event);

      expect(service.notifications.length, equals(1));
      final notif = service.notifications.first;
      expect(notif.title, equals('Compliance Verdict: Failed'));
      expect(notif.category, equals(NotificationCategory.compliance));
      expect(notif.isRead, isFalse);
      expect(notif.body, contains('4C8E7456'));
      expect(notif.body, contains('FAILED'));
      expect(notif.body, contains('Rule 6(1)(e)'));
      expect(notif.body, contains('Net Qty Font Violation'));
      expect(service.unreadCount, equals(1));
    });

    test('Wires scan.status_changed PASSED event into compliance notification', () async {
      final event = AppEvent(
        id: 'evt-002',
        eventType: 'scan.status_changed',
        payload: {
          'scan_id': 'pass-scan-12345678',
          'new_status': 'PASSED',
          'rule_results': [
            {'rule_id': '6(1)(a)', 'status': 'PASS'},
          ],
          'assigned_lmo_id': 'field-officer-01',
        },
        createdAt: DateTime.now(),
      );

      await service.handleEvent(event);

      expect(service.notifications.length, equals(1));
      final notif = service.notifications.first;
      expect(notif.title, equals('Compliance Verdict: Passed'));
      expect(notif.category, equals(NotificationCategory.compliance));
      expect(notif.body, contains('PASSED'));
    });

    test('Wires task.assigned event into task notification', () async {
      final event = AppEvent(
        id: 'evt-003',
        eventType: 'task.assigned',
        payload: {
          'scan_id': 'ecom-scan-99',
          'assigned_to_lmo_id': 'field-officer-01',
          'task_type': 'field_followup',
        },
        createdAt: DateTime.now(),
      );

      await service.handleEvent(event);

      expect(service.notifications.length, equals(1));
      final notif = service.notifications.first;
      expect(notif.title, equals('New Task: Field Follow-up'));
      expect(notif.body, contains('field verification'));
    });

    test('markAllAsRead and markAsRead update unread counter accurately', () async {
      service.addNotification(
        NotificationItem(
          id: 'n1',
          title: 'Notif 1',
          body: 'Body 1',
          category: NotificationCategory.compliance,
          timestamp: DateTime.now(),
          isRead: false,
        ),
      );
      service.addNotification(
        NotificationItem(
          id: 'n2',
          title: 'Notif 2',
          body: 'Body 2',
          category: NotificationCategory.compliance,
          timestamp: DateTime.now(),
          isRead: false,
        ),
      );

      expect(service.unreadCount, equals(2));

      service.markAsRead('n1');
      expect(service.unreadCount, equals(1));
      expect(service.notifications.firstWhere((n) => n.id == 'n1').isRead, isTrue);

      service.markAllAsRead();
      expect(service.unreadCount, equals(0));
    });
  });
}
