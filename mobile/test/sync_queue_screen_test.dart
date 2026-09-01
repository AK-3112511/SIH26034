import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/core/widgets/status_chip.dart';
import 'package:mobile/src/features/scans/models/capture_record.dart';
import 'package:mobile/src/features/scans/presentation/sync_queue_screen.dart';

void main() {
  group('SyncQueueScreen (§2 Screen 6 & §3.1 Stuck State)', () {
    testWidgets('renders empty state when queue is 100% synced', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const SyncQueueScreen(
            initialCaptures: [],
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Offline Sync Queue'), findsOneWidget);
      expect(find.text('Offline Queue is Empty'), findsOneWidget);
      expect(find.text('0 local capture(s) pending'), findsOneWidget);
    });

    testWidgets('renders regular pending/failed items with StatusChip and retry action', (tester) async {
      final record = CaptureRecord(
        localId: 'loc-test-100',
        imagePath: '/tmp/img1.jpg',
        capturedAtUtc: '2026-09-01T14:30:00.000Z',
        referenceObjectType: 'box',
        syncStatus: 'PENDING_UPLOAD',
        retryCount: 2,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SyncQueueScreen(
            initialCaptures: [record],
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('CAPTURE #LOC-TEST'), findsOneWidget);
      expect(find.byType(StatusChip), findsOneWidget);
      expect(find.text('Pending Upload'), findsOneWidget);
      expect(find.text('Auto-retry count: 2/10'), findsOneWidget);
      expect(find.text('RETRY NOW'), findsOneWidget);
      expect(find.text('RETRY ALL'), findsOneWidget);
    });

    testWidgets('renders distinct STUCK capture card when retry_count > 10 (§3.1)', (tester) async {
      final record = CaptureRecord(
        localId: 'loc-stuck-500',
        imagePath: '/tmp/stuck_img.jpg',
        capturedAtUtc: '2026-09-01T10:00:00.000Z',
        referenceObjectType: 'bottle',
        syncStatus: 'FAILED',
        retryCount: 11, // Exceeds 10 retries threshold
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SyncQueueScreen(
            initialCaptures: [record],
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Verify Stuck card visual indicators
      expect(find.text('CAPTURE #LOC-STUC'), findsOneWidget);
      expect(find.text('STUCK (10+ RETRIES)'), findsOneWidget);
      expect(find.textContaining('Automatic background sync suspended'), findsOneWidget);
      expect(find.text('FORCE RETRY'), findsOneWidget);
      expect(find.text('DISCARD'), findsOneWidget);
    });

    testWidgets('tapping Discard shows confirmation dialog and removes stuck item', (tester) async {
      final record = CaptureRecord(
        localId: 'loc-stuck-999',
        imagePath: '/tmp/corrupt.jpg',
        capturedAtUtc: '2026-09-01T08:00:00.000Z',
        referenceObjectType: 'manual',
        syncStatus: 'FAILED',
        retryCount: 12,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: SyncQueueScreen(
            initialCaptures: [record],
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('stuck_discard_btn_loc-stuck-999')), findsOneWidget);
      await tester.tap(find.byKey(const Key('stuck_discard_btn_loc-stuck-999')));
      await tester.pumpAndSettle();

      expect(find.text('Discard Stuck Capture?'), findsOneWidget);

      // Confirm discard
      await tester.tap(find.byKey(const Key('confirm_discard_dialog_btn')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Queue is now empty
      expect(find.text('Offline Queue is Empty'), findsOneWidget);
    });
  });
}
