import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:mobile/src/features/auth/data/auth_service.dart';
import 'package:mobile/src/features/notifications/models/app_event.dart';
import 'package:mobile/src/features/notifications/services/event_polling_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Phase 7.1 Mobile Event Polling & Payload Tests (§6.2)', () {
    test('AppEvent parses scan.status_changed payload per §6.2 specifications', () {
      final json = {
        'id': 'evt-001',
        'event_type': 'scan.status_changed',
        'payload': {
          'scan_id': '4c8e7456-9b1b-4f8a-a123-abcdef123456',
          'new_status': 'FAILED',
          'rule_results': [
            {
              'rule_id': '6_1_e',
              'status': 'FAIL',
              'reason': 'MRP declaration missing tax phrase',
            },
            {
              'rule_id': '6_1_a',
              'status': 'PASS',
              'reason': 'Manufacturer details compliant',
            }
          ],
          'assigned_lmo_id': 'user-lmo-999',
        },
        'created_at': '2026-09-21T10:30:00Z',
      };

      final event = AppEvent.fromJson(json);

      expect(event.id, equals('evt-001'));
      expect(event.eventType, equals('scan.status_changed'));
      expect(event.isScanStatusChanged, isTrue);
      expect(event.isTaskAssigned, isFalse);

      final payload = event.scanStatusChangedPayload;
      expect(payload, isNotNull);
      expect(payload!.scanId, equals('4c8e7456-9b1b-4f8a-a123-abcdef123456'));
      expect(payload.newStatus, equals('FAILED'));
      expect(payload.assignedLmoId, equals('user-lmo-999'));
      expect(payload.ruleResults.length, equals(2));
      expect(payload.ruleResults[0]['rule_id'], equals('6_1_e'));
      expect(payload.ruleResults[0]['status'], equals('FAIL'));
    });

    test('AppEvent parses task.assigned payload per §6.2 specifications', () {
      final json = {
        'id': 'evt-002',
        'event_type': 'task.assigned',
        'payload': {
          'scan_id': 'scan-ecommerce-88',
          'assigned_to_lmo_id': 'field-lmo-42',
          'task_type': 'field_followup',
        },
        'created_at': '2026-09-21T10:35:00Z',
      };

      final event = AppEvent.fromJson(json);

      expect(event.id, equals('evt-002'));
      expect(event.eventType, equals('task.assigned'));
      expect(event.isTaskAssigned, isTrue);
      expect(event.isScanStatusChanged, isFalse);

      final payload = event.taskAssignedPayload;
      expect(payload, isNotNull);
      expect(payload!.scanId, equals('scan-ecommerce-88'));
      expect(payload.assignedToLmoId, equals('field-lmo-42'));
      expect(payload.taskType, equals('field_followup'));
    });

    test('EventPollingService pollOnce executes HTTP GET with auth header and since cursor', () async {
      Uri? capturedUri;
      Map<String, String>? capturedHeaders;

      final mockClient = MockClient((request) async {
        capturedUri = request.url;
        capturedHeaders = request.headers;

        final responseBody = {
          'events': [
            {
              'id': 'evt-100',
              'event_type': 'scan.status_changed',
              'payload': {
                'scan_id': 'scan-100',
                'new_status': 'PASSED',
                'rule_results': [],
                'assigned_lmo_id': 'lmo-01',
              },
              'created_at': '2026-09-21T11:00:00Z',
            }
          ],
          'count': 1,
          'server_time': '2026-09-21T11:00:05Z',
        };

        return http.Response(jsonEncode(responseBody), 200);
      });

      final authService = AuthService();
      final service = EventPollingService.createTestInstance(
        client: mockClient,
        authService: authService,
      );
      service.setLastPollTime('2026-09-21T10:59:00Z');

      final events = await service.pollOnce();

      expect(events.length, equals(1));
      expect(events[0].id, equals('evt-100'));
      expect(events[0].eventType, equals('scan.status_changed'));
      expect(service.lastPollTime, equals('2026-09-21T11:00:05Z'));
      expect(service.receivedEvents.length, equals(1));

      // Verify request parameters
      expect(capturedUri, isNotNull);
      expect(capturedUri!.queryParameters['since'], equals('2026-09-21T10:59:00Z'));
      expect(capturedHeaders!['Content-Type'], equals('application/json'));
    });

    test('EventPollingService broadcasts events to eventStream', () async {
      final mockClient = MockClient((request) async {
        final responseBody = {
          'events': [
            {
              'id': 'evt-200',
              'event_type': 'task.assigned',
              'payload': {
                'scan_id': 'scan-200',
                'assigned_to_lmo_id': 'lmo-test',
                'task_type': 'field_followup',
              },
              'created_at': '2026-09-21T11:10:00Z',
            }
          ],
          'count': 1,
          'server_time': '2026-09-21T11:10:02Z',
        };

        return http.Response(jsonEncode(responseBody), 200);
      });

      final service = EventPollingService.createTestInstance(client: mockClient);

      final streamEvents = <AppEvent>[];
      final subscription = service.eventStream.listen(streamEvents.add);

      await service.pollOnce();
      await Future.delayed(const Duration(milliseconds: 50));

      expect(streamEvents.length, equals(1));
      expect(streamEvents[0].id, equals('evt-200'));
      expect(streamEvents[0].isTaskAssigned, isTrue);

      await subscription.cancel();
      service.dispose();
    });
  });
}
