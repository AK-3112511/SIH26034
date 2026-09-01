import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/core/widgets/calibration_tick_rule.dart';
import 'package:mobile/src/core/widgets/status_chip.dart';
import 'package:mobile/src/features/auth/presentation/login_screen.dart';
import 'package:mobile/src/features/scans/models/capture_item.dart';
import 'package:mobile/src/features/scans/presentation/home_screen.dart';

void main() {
  group('HomeScreen (§2 Screen 2)', () {
    testWidgets('renders default empty state per requirements', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const HomeScreen(initialCaptures: []),
        ),
      );

      // Verify app bar
      expect(find.text('MetrologyAI — Field LMO'), findsOneWidget);

      // Verify calibration tick rule divider
      expect(find.byType(CalibrationTickRule), findsOneWidget);

      // Verify section header
      expect(find.text("Today's Scans"), findsOneWidget);
      expect(find.text('TOTAL: 0'), findsOneWidget);

      // Verify empty state display
      expect(find.text('No Captures Recorded Today'), findsOneWidget);

      // Verify bottom-anchored "New Scan" button
      expect(find.text('NEW SCAN (AR GUIDE)'), findsOneWidget);
    });

    testWidgets('renders capture items with flat pill status chips when items exist', (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockCaptures = CaptureItem.mockItems();

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: HomeScreen(initialCaptures: mockCaptures),
        ),
      );

      // Verify metrics summary count
      expect(find.text('TOTAL: 3'), findsOneWidget);

      // Verify product items exist
      expect(find.text('Parle-G Glucose Biscuits 100g'), findsOneWidget);
      expect(find.text('Amul Pasteurised Butter 500g'), findsOneWidget);
      expect(find.text('Maggi 2-Minute Noodles 70g'), findsOneWidget);

      // Verify all 3 flat pill sync status chips are rendered (§5.4)
      expect(find.byType(StatusChip), findsNWidgets(3));
      expect(find.text('Synced'), findsOneWidget); // in capture chip
      expect(find.text('SYNCED'), findsOneWidget); // in metric card
      expect(find.text('Pending Upload'), findsOneWidget); // in capture chip
      expect(find.text('PENDING'), findsOneWidget); // in metric card
      expect(find.text('Failed'), findsOneWidget); // in capture chip
      expect(find.text('FAILED'), findsOneWidget); // in metric card
    });

    testWidgets('tapping preview button toggles between mock data and empty state', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const HomeScreen(initialCaptures: []),
        ),
      );

      expect(find.text('No Captures Recorded Today'), findsOneWidget);

      // Tap Preview button
      await tester.tap(find.text('Preview'));
      await tester.pumpAndSettle();

      expect(find.text('No Captures Recorded Today'), findsNothing);
      expect(find.text('Parle-G Glucose Biscuits 100g'), findsOneWidget);

      // Tap Empty button
      await tester.tap(find.text('Empty'));
      await tester.pumpAndSettle();

      expect(find.text('No Captures Recorded Today'), findsOneWidget);
    });

    testWidgets('tapping logout redirects to LoginScreen', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const HomeScreen(initialCaptures: []),
        ),
      );

      // First pump to settle the initial state
      await tester.pumpAndSettle();

      // Find and tap logout button on AppBar
      final logoutButton = find.byIcon(Icons.logout);
      expect(logoutButton, findsOneWidget);

      await tester.tap(logoutButton);
      // pump multiple frames to allow the async logout() + navigation to complete
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.text('AUTHENTICATE & ENTER FIELD MODE'), findsOneWidget);
    });
  });
}
