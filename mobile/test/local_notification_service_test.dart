import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/features/notifications/services/local_notification_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Phase 7.2 LocalNotificationService (§5.2 Lockscreen Push)', () {
    test('Channel configuration constants match high-importance specifications', () {
      expect(LocalNotificationService.kComplianceChannelId,
          equals('metrologyai_compliance_channel'));
      expect(LocalNotificationService.kComplianceChannelName,
          equals('Compliance & Verdict Alerts'));
      expect(
        LocalNotificationService.kComplianceChannelDescription,
        contains('§5.2'),
      );
    });

    test('initialize() and requestPermissions() execute safely in test environment', () async {
      final service = LocalNotificationService.createTestInstance();
      await service.initialize();

      final result = await service.requestPermissions();
      expect(result, isTrue);
    });

    test('showComplianceNotification() formats and displays alert without platform error', () async {
      final service = LocalNotificationService.createTestInstance();

      await service.showComplianceNotification(
        title: 'Compliance Verdict: Failed',
        body: 'Your scan #4C8E7456 confirmed FAILED — Rule 6(1)(e) (Net Qty Font Violation).',
        payload: '4c8e7456-9b1b-4f8a-a123-abcdef123456',
        notificationId: 101,
      );

      // Verify execution completes smoothly
      expect(service, isNotNull);
    });
  });
}
