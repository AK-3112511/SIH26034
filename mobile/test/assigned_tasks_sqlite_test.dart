import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/src/core/database/database_helper.dart';
import 'package:mobile/src/features/notifications/models/app_event.dart';
import 'package:mobile/src/features/notifications/services/event_polling_service.dart';
import 'package:mobile/src/features/scans/models/assigned_task_record.dart';
import 'package:mobile/src/features/scans/services/assigned_tasks_service.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // Initialize SQLite FFI for in-memory desktop testing
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  late Database db;
  late DatabaseHelper dbHelper;

  setUp(() async {
    db = await databaseFactory.openDatabase(inMemoryDatabasePath);
    // Use the app's own schema rather than a copy, so a migration that misses
    // a column fails here instead of on a field officer's handset.
    await DatabaseHelper.createSchema(db);

    dbHelper = DatabaseHelper();
    dbHelper.setDatabase(db);
  });

  tearDown(() async {
    await db.close();
  });

  group('Phase 7.3: Assigned Tasks SQLite Persistence & Hydration (§5.3)', () {
    test('DatabaseHelper persists assigned task and retrieves it across queries', () async {
      const task = AssignedTaskRecord(
        scanId: 'scan-ecom-101',
        title: 'Fortune Sunflower Oil 1L',
        category: 'Blinkit Packaging Follow-up',
        platform: 'Blinkit',
        location: 'Dark Store 12, Madurai',
        assignedAtUtc: '2026-09-21T10:00:00Z',
        taskType: 'field_followup',
        status: 'PENDING',
        instructions: 'Check font size compliance and issue Section 39 notice.',
      );

      await dbHelper.insertAssignedTask(task);

      final loaded = await dbHelper.getAllAssignedTasks();
      expect(loaded.length, equals(1));
      expect(loaded.first.scanId, equals('scan-ecom-101'));
      expect(loaded.first.title, equals('Fortune Sunflower Oil 1L'));
      expect(loaded.first.platform, equals('Blinkit'));
      expect(loaded.first.instructions, contains('Section 39 notice'));

      // Delete task
      await dbHelper.deleteAssignedTask('scan-ecom-101');
      final empty = await dbHelper.getAllAssignedTasks();
      expect(empty.isEmpty, isTrue);
    });

    test('AssignedTasksService ingests real-time task.assigned event and persists to SQLite', () async {
      final mockClient = MockClient((request) async {
        return http.Response('[]', 200);
      });

      final service = AssignedTasksService.createTestInstance(
        databaseHelper: dbHelper,
        eventPollingService: EventPollingService(),
        httpClient: mockClient,
      );

      final event = AppEvent(
        id: 'evt-task-01',
        eventType: 'task.assigned',
        payload: {
          'scan_id': '4c8e7456-9b1b-4f8a-a123-abcdef123456',
          'assigned_to_lmo_id': 'officer-uuid-01',
          'task_type': 'field_followup',
        },
        createdAt: DateTime.parse('2026-09-21T10:30:00Z'),
      );

      await service.handleTaskAssignedEvent(event);

      // Verify in-memory state
      expect(service.count, equals(1));
      expect(service.assignedItems.first.id, equals('TASK-4C8E7456'));
      expect(service.assignedItems.first.isAssignedTask, isTrue);

      // Verify SQLite state survived
      final dbTasks = await dbHelper.getAllAssignedTasks();
      expect(dbTasks.length, equals(1));
      expect(dbTasks.first.scanId, equals('4c8e7456-9b1b-4f8a-a123-abcdef123456'));
    });

    test('AssignedTasksService hydrates from remote API GET /scans/assigned-to-me into SQLite', () async {
      final mockApiResponse = [
        {
          'scan_id': 'ecom-blinkit-99',
          'source': 'ecommerce',
          'status': 'FAILED',
          'image_url': 'http://127.0.0.1:8000/static/uploads/blinkit.jpg',
          'product_name': 'Haldiram Bhujia 400g',
          'platform': 'Blinkit',
          'task_type': 'field_followup',
          'assigned_at_utc': '2026-09-21T09:00:00Z',
          'reviewer_note': 'Missing tax phrase on MRP',
          'instructions': 'Physical inspection of dark store inventory required',
          'rule_violations': ['6_1_e: MRP declaration missing tax phrase'],
        }
      ];

      final mockClient = MockClient((request) async {
        if (request.url.path.contains('/scans/assigned-to-me')) {
          return http.Response(jsonEncode(mockApiResponse), 200);
        }
        return http.Response('Not Found', 404);
      });

      final service = AssignedTasksService.createTestInstance(
        databaseHelper: dbHelper,
        eventPollingService: EventPollingService(),
        httpClient: mockClient,
      );

      // Test loadLocalTasks hydrates empty list initially
      await service.loadLocalTasks();
      expect(service.count, equals(0));

      // Ingest and verify conversion to CaptureItem
      final record = AssignedTaskRecord(
        scanId: 'ecom-blinkit-99',
        title: 'Haldiram Bhujia 400g',
        category: 'Blinkit Violation Follow-up',
        platform: 'Blinkit',
        location: 'Assigned Merchant Site',
        assignedAtUtc: '2026-09-21T09:00:00Z',
        taskType: 'field_followup',
        instructions: 'Physical inspection of dark store inventory required',
      );
      await dbHelper.insertAssignedTask(record);

      await service.loadLocalTasks();
      expect(service.count, equals(1));
      final captureItem = service.assignedItems.first;
      expect(captureItem.productName, equals('Haldiram Bhujia 400g'));
      expect(captureItem.platform, equals('Blinkit'));
      expect(captureItem.isAssignedTask, isTrue);
      expect(captureItem.followUpNote, contains('Physical inspection'));
    });
  });
}
