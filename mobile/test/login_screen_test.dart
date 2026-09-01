import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/core/widgets/calibration_tick_rule.dart';
import 'package:mobile/src/features/auth/data/auth_service.dart';
import 'package:mobile/src/features/auth/presentation/login_screen.dart';
import 'package:mobile/src/features/scans/presentation/home_screen.dart';

void main() {
  group('LoginScreen (§2 Screen 1)', () {
    testWidgets('renders all official UI elements without hardcoded credentials', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const LoginScreen(),
        ),
      );

      // Verify government header & title
      expect(find.text('LEGAL METROLOGY DIVISION'), findsOneWidget);
      expect(find.text('MetrologyAI Mobile'), findsOneWidget);
      expect(find.byIcon(Icons.shield_outlined), findsOneWidget);

      // Verify signature calibration ruler divider
      expect(find.byType(CalibrationTickRule), findsOneWidget);

      // Verify form labels and input fields
      expect(find.text('OFFICIAL USERNAME OR EMAIL'), findsOneWidget);
      expect(find.text('SECURITY CREDENTIAL / PASSWORD'), findsOneWidget);
      expect(find.text('AUTHENTICATE & ENTER FIELD MODE'), findsOneWidget);

      // Verify NO demo credentials buttons exist
      expect(find.text('Quick Demo Login'), findsNothing);
      expect(find.textContaining('lmo_ramesh'), findsNothing);
      expect(find.textContaining('Inspect#2026'), findsNothing);
    });

    testWidgets('validates required fields on submission', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const LoginScreen(),
        ),
      );

      // Tap submit with empty fields
      await tester.tap(find.text('AUTHENTICATE & ENTER FIELD MODE'));
      await tester.pumpAndSettle();

      expect(find.text('Officer username or email is required'), findsOneWidget);
      expect(find.text('Security password is required'), findsOneWidget);
    });

    testWidgets('successful authentication navigates to HomeScreen', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          '''
          {
            "access_token": "fake-jwt-token-xyz",
            "token_type": "bearer",
            "user": {
              "id": "123e4567-e89b-12d3-a456-426614174000",
              "username": "lmo_ramesh",
              "email": "ramesh@legalmetrology.gov.in",
              "full_name": "Ramesh Kumar",
              "role": "field_lmo",
              "district": "Coimbatore",
              "is_active": true,
              "created_at": "2026-09-01T10:00:00Z"
            }
          }
          ''',
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final authService = AuthService();
      authService.setClient(mockClient);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: LoginScreen(authService: authService),
        ),
      );

      await tester.enterText(
        find.widgetWithText(TextFormField, '').first,
        'lmo_ramesh',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, '').last,
        'SecretPassword123',
      );

      await tester.tap(find.text('AUTHENTICATE & ENTER FIELD MODE'));
      // Use bounded pump instead of pumpAndSettle — HomeScreen's DB init is async
      // and would cause pumpAndSettle to wait indefinitely in the test host environment.
      await tester.pump();
      await tester.pump(const Duration(seconds: 3));

      // Should have navigated to HomeScreen
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(find.text('MetrologyAI — Field LMO'), findsOneWidget);
    });
  });
}
