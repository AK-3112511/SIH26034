import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/features/capture/presentation/capture_screen.dart';

void main() {
  group('CaptureScreen (§2 Screen 3 & §4.1 Layout Sketch)', () {
    testWidgets('renders all §4.1 layout controls and disabled shutter initial state', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const CaptureScreen(forceSimulator: true),
        ),
      );

      // Verify top controls: Back and Flash
      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
      expect(find.byIcon(Icons.flash_off), findsOneWidget);

      // Verify guide box initial text
      expect(find.text('PLACE CARD HERE'), findsOneWidget);

      // Verify product type choices: ( Box ) ( Bottle ) ( Manual )
      expect(find.text('Box'), findsOneWidget);
      expect(find.text('Bottle'), findsOneWidget);
      expect(find.text('Manual'), findsOneWidget);

      // Verify helper instruction
      expect(find.text('Place a debit/PAN card next to the product'), findsOneWidget);

      // Verify shutter button is initially disabled / locked
      expect(find.byIcon(Icons.lock_outline), findsOneWidget);
      expect(find.byIcon(Icons.camera_alt), findsNothing);
    });

    testWidgets('simulating card detection enables shutter and animates guide box', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const CaptureScreen(forceSimulator: true),
        ),
      );

      expect(find.text('PLACE CARD HERE'), findsOneWidget);
      expect(find.byIcon(Icons.lock_outline), findsOneWidget);

      // Tap the simulator card toggle button
      await tester.tap(find.text('Simulate Reference Card'));
      await tester.pumpAndSettle();

      // Guide box should now indicate card detected
      expect(find.text('CARD DETECTED'), findsOneWidget);

      // Shutter should now be unlocked with camera icon (brass-500 accent ready state)
      expect(find.byIcon(Icons.camera_alt), findsOneWidget);
      expect(find.byIcon(Icons.lock_outline), findsNothing);
    });

    testWidgets('product type selector updates selection state', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const CaptureScreen(forceSimulator: true),
        ),
      );

      // Select Bottle product type
      await tester.tap(find.text('Bottle'));
      await tester.pumpAndSettle();

      final bottleChip = tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Bottle'));
      expect(bottleChip.selected, isTrue);

      final boxChip = tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Box'));
      expect(boxChip.selected, isFalse);
    });

    testWidgets('tapping flash button toggles flash mode', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const CaptureScreen(forceSimulator: true),
        ),
      );

      expect(find.byIcon(Icons.flash_off), findsOneWidget);

      await tester.tap(find.byIcon(Icons.flash_off));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.flash_on), findsOneWidget);
    });
  });
}
