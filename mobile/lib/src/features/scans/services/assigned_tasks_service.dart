import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../../../core/constants/api_constants.dart';
import '../../../core/database/database_helper.dart';
import '../../../core/widgets/status_chip.dart';
import '../../auth/data/auth_service.dart';
import '../../notifications/models/app_event.dart';
import '../../notifications/services/event_polling_service.dart';
import '../models/assigned_task_record.dart';
import '../models/capture_item.dart';
import '../../../core/utils/short_id.dart';

/// Coordinator service for managing assigned field tasks per §5.3.
///
/// Features:
/// 1. Durable SQLite persistence in `assigned_tasks` table across app kills
/// 2. Hydration from `GET /api/v1/scans/assigned-to-me` on app launch
/// 3. Real-time ingestion of `task.assigned` events from [EventPollingService]
class AssignedTasksService extends ChangeNotifier {
  static final AssignedTasksService _instance = AssignedTasksService._internal();
  factory AssignedTasksService() => _instance;

  @visibleForTesting
  factory AssignedTasksService.createTestInstance({
    DatabaseHelper? databaseHelper,
    EventPollingService? eventPollingService,
    http.Client? httpClient,
  }) {
    return AssignedTasksService._internal(
      databaseHelper: databaseHelper,
      eventPollingService: eventPollingService,
      httpClient: httpClient,
    );
  }

  AssignedTasksService._internal({
    DatabaseHelper? databaseHelper,
    EventPollingService? eventPollingService,
    http.Client? httpClient,
  })  : _dbHelper = databaseHelper ?? DatabaseHelper(),
        _eventPollingService = eventPollingService ?? EventPollingService(),
        _httpClient = httpClient ?? http.Client() {
    _initEventSubscription();
  }

  final DatabaseHelper _dbHelper;
  final EventPollingService _eventPollingService;
  final http.Client _httpClient;
  StreamSubscription<AppEvent>? _eventSubscription;

  List<AssignedTaskRecord> _tasks = [];
  bool _isLoading = false;

  List<AssignedTaskRecord> get tasks => List.unmodifiable(_tasks);
  bool get isLoading => _isLoading;
  int get count => _tasks.length;

  List<CaptureItem> get assignedItems => _tasks.map(recordToCaptureItem).toList();

  void _initEventSubscription() {
    _eventSubscription = _eventPollingService.eventStream.listen((event) {
      if (event.isTaskAssigned) {
        handleTaskAssignedEvent(event);
      }
    });
  }

  /// Ingest real-time `task.assigned` event and persist immediately to SQLite
  Future<void> handleTaskAssignedEvent(AppEvent event) async {
    final payload = event.taskAssignedPayload;
    if (payload == null) return;

    final displayId = shortId(payload.scanId);

    final record = AssignedTaskRecord(
      scanId: payload.scanId,
      title: 'E-Commerce Package #$displayId',
      category: 'E-Commerce Violation Follow-up',
      platform: 'Blinkit',
      location: 'Seller Verification Premises',
      assignedAtUtc: event.createdAt.toUtc().toIso8601String(),
      taskType: payload.taskType,
      status: 'PENDING',
      instructions:
          'Conduct a physical on-site inspection and serve a Section 39 compliance notice.',
    );

    await _dbHelper.insertAssignedTask(record);

    // Update in-memory list (replace if existing, else prepend)
    _tasks.removeWhere((t) => t.scanId == record.scanId);
    _tasks.insert(0, record);
    notifyListeners();
  }

  /// Load tasks from local SQLite database (instant offline hydration)
  Future<void> loadLocalTasks() async {
    try {
      final local = await _dbHelper.getAllAssignedTasks();
      _tasks = local;
      notifyListeners();
    } catch (e) {
      debugPrint('[AssignedTasksService] Error reading SQLite: $e');
    }
  }

  /// Sync assigned tasks from backend API: GET /scans/assigned-to-me
  Future<void> syncRemoteTasks() async {
    final token = AuthService().token;
    if (token == null || token.isEmpty) {
      await loadLocalTasks();
      return;
    }

    _isLoading = true;
    notifyListeners();

    try {
      final response = await _httpClient.get(
        Uri.parse(ApiConstants.scansAssignedToMeEndpoint),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final List<dynamic> jsonList = jsonDecode(response.body) as List<dynamic>;
        final records = jsonList.map((item) {
          final map = item as Map<String, dynamic>;
          final scanId = map['scan_id'] as String? ?? '';
          final productName = map['product_name'] as String? ?? 'E-Commerce Package';
          final platform = map['platform'] as String? ?? 'E-Commerce';
          final instructions = map['instructions'] as String? ?? '';
          final assignedAt = map['assigned_at_utc'] as String? ??
              DateTime.now().toUtc().toIso8601String();

          return AssignedTaskRecord(
            scanId: scanId,
            title: productName,
            category: '$platform Violation Follow-up',
            platform: platform,
            location: 'Assigned Merchant Site',
            assignedAtUtc: assignedAt,
            taskType: map['task_type'] as String? ?? 'field_followup',
            status: map['status'] as String? ?? 'PENDING',
            instructions: instructions,
          );
        }).toList();

        // Batch persist to SQLite
        await _dbHelper.insertAssignedTasks(records);
        _tasks = records;
      }
    } catch (e) {
      debugPrint('[AssignedTasksService] Network sync error, retaining local SQLite cache: $e');
      // On network failure, retain and re-hydrate SQLite data
      await loadLocalTasks();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Helper to convert SQLite record into Home screen CaptureItem
  static CaptureItem recordToCaptureItem(AssignedTaskRecord r) {
    DateTime parsedTime;
    try {
      parsedTime = DateTime.parse(r.assignedAtUtc).toLocal();
    } catch (_) {
      parsedTime = DateTime.now();
    }

    final displayId = shortId(r.scanId);

    return CaptureItem(
      id: 'TASK-$displayId',
      productName: r.title,
      category: r.category,
      timestamp: parsedTime,
      location: r.location,
      syncStatus: SyncStatus.synced,
      origin: CaptureOrigin.assignedTask,
      platform: r.platform,
      taskType: r.taskType,
      followUpNote: r.instructions,
    );
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    super.dispose();
  }
}
