import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/design_tokens.dart';
import 'package:mobile/src/core/widgets/status_chip.dart';

void main() {
  group('StatusChip (§5.4 Flat Pill Shape)', () {
    testWidgets('renders Synced status chip with correct color and label', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusChip(status: SyncStatus.synced),
          ),
        ),
      );

      expect(find.text('Synced'), findsOneWidget);
      expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);

      // Verify flat pill shape container (distinct from circular seal badge)
      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      expect(decoration.borderRadius, BorderRadius.circular(AppRadius.sealBadge));
      expect(decoration.border?.top.color, AppColors.verdictPass);
    });

    testWidgets('renders Pending Upload status chip with correct color and label', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusChip(status: SyncStatus.pendingUpload),
          ),
        ),
      );

      expect(find.text('Pending Upload'), findsOneWidget);
      expect(find.byIcon(Icons.cloud_upload_outlined), findsOneWidget);

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      expect(decoration.border?.top.color, AppColors.verdictPending);
    });

    testWidgets('renders Failed status chip with correct color and label', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StatusChip(status: SyncStatus.failed),
          ),
        ),
      );

      expect(find.text('Failed'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      expect(decoration.border?.top.color, AppColors.verdictFail);
    });
  });
}
