import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/features/notifications/models/notification_item.dart';
import 'package:mobile/src/features/notifications/presentation/notifications_screen.dart';

void main() {
  group('NotificationsScreen (§2 Screen 7)', () {
    testWidgets('renders official notification feed with mock items', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const NotificationsScreen(),
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
          home: const NotificationsScreen(),
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
          home: const NotificationsScreen(),
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
  });
}
