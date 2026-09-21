import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/core/widgets/status_chip.dart';
import 'package:mobile/src/features/scans/models/capture_item.dart';
import 'package:mobile/src/features/scans/presentation/home_screen.dart';

void main() {
  group('Phase 7.3: Mobile Home Screen Distinction — My Captures vs Assigned Tasks (§5.3)', () {
    final now = DateTime.now();

    final testItems = [
      CaptureItem(
        id: 'SCAN-2026-CAP01',
        productName: 'Parle-G Glucose Biscuits 100g',
        category: 'Rigid Paperboard Box',
        timestamp: now.subtract(const Duration(minutes: 15)),
        location: 'Sri Murugan Provisions, Gandhipuram',
        syncStatus: SyncStatus.synced,
        origin: CaptureOrigin.selfCaptured,
      ),
      CaptureItem(
        id: 'SCAN-2026-CAP02',
        productName: 'Amul Pasteurised Butter 500g',
        category: 'Paperboard Outer Carton',
        timestamp: now.subtract(const Duration(minutes: 30)),
        location: 'Heritage Mart, RS Puram',
        syncStatus: SyncStatus.pendingUpload,
        origin: CaptureOrigin.selfCaptured,
      ),
      CaptureItem(
        id: 'SCAN-ECOM-BLK01',
        productName: 'Fortune Sunlite Refined Sunflower Oil 1L',
        category: 'E-Commerce Packaging Follow-up',
        timestamp: now.subtract(const Duration(hours: 1)),
        location: 'Blinkit Dark Store #42, Madurai Central',
        syncStatus: SyncStatus.synced,
        origin: CaptureOrigin.assignedTask,
        platform: 'Blinkit',
        taskType: 'field_followup',
        assignedBy: 'Senior LMO Priya Sharma',
        followUpNote:
            'Rule 6(1)(e) Net Qty Font Violation (1.2mm < 3.0mm mandated). Physical stock verification & Section 39 notice required.',
      ),
    ];

    testWidgets('HomeScreen renders visual distinction between self-captured scans and assigned tasks', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: HomeScreen(initialCaptures: testItems),
        ),
      );
      await tester.pumpAndSettle();

      // Total count across all items
      expect(find.text('TOTAL: 3'), findsOneWidget);

      // Verify filter tabs are present with item counts
      expect(find.text('All'), findsOneWidget);
      expect(find.text('My Captures'), findsOneWidget);
      expect(find.text('Assigned to Me'), findsOneWidget);

      // Verify explicit badges differentiating origin (§5.3)
      expect(find.text('FIELD CAPTURE'), findsNWidgets(2));
      expect(find.text('ASSIGNED TASK (§5.3)'), findsOneWidget);
      expect(find.text('BLINKIT'), findsOneWidget);

      // Verify assigned task follow-up note preview is visible
      expect(
        find.textContaining('Rule 6(1)(e) Net Qty Font Violation'),
        findsOneWidget,
      );
    });

    testWidgets('Filtering by My Captures and Assigned to Me toggles visibility correctly', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: HomeScreen(initialCaptures: testItems),
        ),
      );
      await tester.pumpAndSettle();

      // Step 1: Tap "My Captures" tab
      await tester.tap(find.text('My Captures'));
      await tester.pumpAndSettle();

      expect(find.text('TOTAL: 2'), findsOneWidget);
      expect(find.text('Parle-G Glucose Biscuits 100g'), findsOneWidget);
      expect(find.text('Amul Pasteurised Butter 500g'), findsOneWidget);
      expect(find.text('Fortune Sunlite Refined Sunflower Oil 1L'), findsNothing);

      // Step 2: Tap "Assigned to Me" tab
      await tester.tap(find.text('Assigned to Me'));
      await tester.pumpAndSettle();

      expect(find.text('TOTAL: 1'), findsOneWidget);
      expect(find.text('Fortune Sunlite Refined Sunflower Oil 1L'), findsOneWidget);
      expect(find.text('Parle-G Glucose Biscuits 100g'), findsNothing);
      expect(find.text('Amul Pasteurised Butter 500g'), findsNothing);

      // Step 3: Tap "All" tab to restore full view
      await tester.tap(find.text('All'));
      await tester.pumpAndSettle();

      expect(find.text('TOTAL: 3'), findsOneWidget);
      expect(find.text('Fortune Sunlite Refined Sunflower Oil 1L'), findsOneWidget);
      expect(find.text('Parle-G Glucose Biscuits 100g'), findsOneWidget);
    });

    testWidgets('Tapping assigned task card opens bottom sheet with follow-up instructions', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: HomeScreen(initialCaptures: testItems),
        ),
      );
      await tester.pumpAndSettle();

      // Tap the assigned task card
      await tester.tap(find.text('Fortune Sunlite Refined Sunflower Oil 1L'));
      await tester.pumpAndSettle();

      // Verify bottom sheet appears
      expect(find.text('Assigned Task Details (§5.3)'), findsOneWidget);
      expect(find.text('INSPECTION INSTRUCTIONS'), findsOneWidget);
      expect(find.text('START ON-SITE INSPECTION'), findsOneWidget);

      // Close bottom sheet
      await tester.tap(find.byIcon(Icons.close));
      await tester.pumpAndSettle();
      expect(find.text('Assigned Task Details (§5.3)'), findsNothing);
    });
  });
}
