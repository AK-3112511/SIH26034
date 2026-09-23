import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/features/capture/presentation/capture_screen.dart';
import 'package:mobile/src/features/capture/services/location_service.dart';

Position _fixAt(double lat, double lng) => Position(
      latitude: lat,
      longitude: lng,
      timestamp: DateTime.now(),
      accuracy: 8.0,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );

/// A location service that reports a good fix without touching the platform.
LocationService _locatedService() {
  final service = LocationService.createTestInstance();
  service.isServiceEnabledOverride = () async => true;
  service.checkPermissionOverride = () async => LocationPermission.whileInUse;
  service.getPositionOverride = () async => _fixAt(13.0827, 80.2707);
  return service;
}

/// A location service where the officer has denied the permission.
LocationService _deniedService() {
  final service = LocationService.createTestInstance();
  service.isServiceEnabledOverride = () async => true;
  service.checkPermissionOverride = () async => LocationPermission.denied;
  service.requestPermissionOverride = () async => LocationPermission.denied;
  return service;
}

Future<void> _pumpCapture(WidgetTester tester, LocationService location) async {
  tester.view.physicalSize = const Size(900, 1800);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });

  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.lightTheme,
      home: CaptureScreen(forceSimulator: true, locationService: location),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  group('CaptureScreen', () {
    testWidgets('renders capture controls with the shutter initially locked', (tester) async {
      await _pumpCapture(tester, _locatedService());

      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
      expect(find.byIcon(Icons.flash_off), findsOneWidget);
      expect(find.text('PLACE CARD HERE'), findsOneWidget);

      // Reference card and package shape are separate questions.
      expect(find.text('REFERENCE CARD'), findsOneWidget);
      expect(find.text('PACKAGE SHAPE'), findsOneWidget);
      expect(find.text('Debit / Credit card'), findsOneWidget);
      expect(find.text('PAN card'), findsOneWidget);
      expect(find.text('Box'), findsOneWidget);
      expect(find.text('Bottle'), findsOneWidget);
      expect(find.text('Other'), findsOneWidget);

      expect(find.text('Place a debit or PAN card flat beside the product.'), findsOneWidget);

      expect(find.byIcon(Icons.lock_outline), findsOneWidget);
      expect(find.byIcon(Icons.camera_alt), findsNothing);
    });

    testWidgets('a detected card with a GPS fix unlocks the shutter', (tester) async {
      await _pumpCapture(tester, _locatedService());

      expect(find.byIcon(Icons.lock_outline), findsOneWidget);

      await tester.tap(find.text('Simulate reference card'));
      await tester.pumpAndSettle();

      expect(find.text('CARD DETECTED'), findsOneWidget);
      expect(find.byIcon(Icons.camera_alt), findsOneWidget);
      expect(find.byIcon(Icons.lock_outline), findsNothing);
    });

    testWidgets('without location the shutter stays locked even with a card in frame',
        (tester) async {
      // The Section 65B hash binds the photo to coordinates. No fix means no
      // attributable evidence, so the capture is refused rather than faked.
      await _pumpCapture(tester, _deniedService());

      expect(
        find.text('Location is required before you can capture evidence.'),
        findsOneWidget,
      );
      expect(
        find.textContaining('needs location access'),
        findsOneWidget,
      );

      await tester.tap(find.text('Simulate reference card'));
      await tester.pumpAndSettle();

      expect(find.text('CARD DETECTED'), findsOneWidget);
      // Card found, but still locked: both conditions are required.
      expect(find.byIcon(Icons.lock_outline), findsOneWidget);
      expect(find.byIcon(Icons.camera_alt), findsNothing);
    });

    testWidgets('package shape selector updates selection state', (tester) async {
      await _pumpCapture(tester, _locatedService());

      await tester.tap(find.text('Bottle'));
      await tester.pumpAndSettle();

      final bottleChip = tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Bottle'));
      expect(bottleChip.selected, isTrue);

      final boxChip = tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Box'));
      expect(boxChip.selected, isFalse);
    });

    testWidgets('reference card selector is independent of package shape', (tester) async {
      await _pumpCapture(tester, _locatedService());

      await tester.tap(find.text('PAN card'));
      await tester.pumpAndSettle();

      final panChip = tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'PAN card'));
      expect(panChip.selected, isTrue);

      // Choosing a different card must not disturb the package shape.
      final boxChip = tester.widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Box'));
      expect(boxChip.selected, isTrue);
    });

    testWidgets('tapping flash button toggles flash mode', (tester) async {
      await _pumpCapture(tester, _locatedService());

      expect(find.byIcon(Icons.flash_off), findsOneWidget);

      await tester.tap(find.byIcon(Icons.flash_off));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.flash_on), findsOneWidget);
    });
  });
}
