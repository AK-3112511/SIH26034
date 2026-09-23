import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/features/notifications/models/app_event.dart';
import 'package:mobile/src/features/notifications/models/notification_item.dart';
import 'package:mobile/src/features/notifications/presentation/notifications_screen.dart';
import 'package:mobile/src/features/notifications/services/notification_service.dart';

/// Feed fixtures. The app no longer ships seeded notifications, so a test
/// that wants a populated feed supplies one.
List<NotificationItem> sampleFeed() {
  final now = DateTime.now();
  return [
    NotificationItem(
      id: 'notif-001',
      title: 'Compliance Verdict: Failed',
      body: 'Rule 6(1)(e) net quantity font violation.',
      category: NotificationCategory.compliance,
      timestamp: now.subtract(const Duration(minutes: 12)),
    ),
    NotificationItem(
      id: 'notif-002',
      title: 'Sync Queue: 3 Scans Ingested',
      body: '3 offline captures uploaded.',
      category: NotificationCategory.syncEvent,
      timestamp: now.subtract(const Duration(hours: 1)),
    ),
    NotificationItem(
      id: 'notif-003',
      title: 'Queue Alert: Photo Stuck',
      body: 'A capture exceeded its upload retries.',
      category: NotificationCategory.stuckAlert,
      timestamp: now.subtract(const Duration(hours: 3)),
    ),
  ];
}

void main() {
  group('NotificationsScreen (§2 Screen 7)', () {
    testWidgets('renders official notification feed', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: NotificationsScreen(initialNotifications: sampleFeed()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Field Notifications'), findsOneWidget);
      expect(find.text('MARK ALL READ'), findsOneWidget);

      // Verify category filter chips
      expect(find.text('All'), findsOneWidget);
      expect(find.text('Compliance'), findsOneWidget);
      expect(find.text('Sync & Queue'), findsOneWidget);
      expect(find.text('Notices'), findsOneWidget);

      // Verify notification headlines
      expect(find.text('Compliance Verdict: Failed'), findsOneWidget);
      expect(find.text('Sync Queue: 3 Scans Ingested'), findsOneWidget);
      expect(find.text('Queue Alert: Photo Stuck'), findsOneWidget);
    });

    testWidgets('filtering by Compliance shows only compliance notifications', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: NotificationsScreen(initialNotifications: sampleFeed()),
        ),
      );
      await tester.pumpAndSettle();

      // Tap 'Compliance' filter chip
      await tester.tap(find.text('Compliance'));
      await tester.pumpAndSettle();

      expect(find.text('Compliance Verdict: Failed'), findsOneWidget);
      expect(find.text('Sync Queue: 3 Scans Ingested'), findsNothing);
      expect(find.text('Queue Alert: Photo Stuck'), findsNothing);
    });

    testWidgets('tapping Mark All Read marks all items as read and dismisses header action', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: NotificationsScreen(initialNotifications: sampleFeed()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('MARK ALL READ'), findsOneWidget);
      await tester.tap(find.text('MARK ALL READ'));
      await tester.pump();
      await tester.pump(const Duration(seconds: 2));

      // After marking all read, the action disappears
      expect(find.text('MARK ALL READ'), findsNothing);
    });

    testWidgets('a fresh install shows an empty feed, not seeded alerts', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: NotificationsScreen(
            notificationService: NotificationService.createTestInstance(
              initialNotifications: const [],
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('No Notifications'), findsOneWidget);
      expect(find.text('Section 39 Challan Dispatched'), findsNothing);
      expect(find.textContaining('Britannia'), findsNothing);
    });

    testWidgets('renders empty state when filter has no items', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: NotificationsScreen(
            initialNotifications: [
              NotificationItem(
                id: 'n1',
                title: 'Only Notice',
                body: 'Notice text',
                category: NotificationCategory.challanNotice,
                timestamp: DateTime.now(),
              ),
            ],
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Filter by Compliance (which has 0 items)
      await tester.tap(find.text('Compliance'));
      await tester.pumpAndSettle();

      expect(find.text('No Notifications'), findsOneWidget);
    });

    testWidgets('dynamically renders live compliance notification when scan.status_changed arrives (§5.2)', (tester) async {
      final notifService = NotificationService.createTestInstance(
        initialNotifications: [],
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: NotificationsScreen(
            notificationService: notifService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('No Notifications'), findsOneWidget);

      // Simulate incoming scan.status_changed event
      final event = AppEvent(
        id: 'evt-live-1',
        eventType: 'scan.status_changed',
        payload: {
          'scan_id': '4c8e7456-9b1b-4f8a-a123-abcdef123456',
          'new_status': 'FAILED',
          'rule_results': [
            {
              'rule_id': '6(1)(e)',
              'status': 'FAIL',
              'reason': 'MRP Net Qty Font Violation',
            }
          ],
          'assigned_lmo_id': 'field-lmo-01',
        },
        createdAt: DateTime.now(),
      );

      await notifService.handleEvent(event);
      await tester.pumpAndSettle();

      expect(find.text('Compliance Verdict: Failed'), findsOneWidget);
      expect(find.textContaining('4C8E7456 was confirmed FAILED'), findsOneWidget);
      expect(find.textContaining('Rule 6(1)(e)'), findsOneWidget);
    });
  });
}

