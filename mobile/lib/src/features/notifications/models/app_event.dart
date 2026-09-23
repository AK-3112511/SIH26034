/// Real-time App Event Models per §6.2
///
/// Implements the two event types:
/// 1. scan.status_changed: { scan_id, new_status, rule_results[], assigned_lmo_id }
/// 2. task.assigned: { scan_id, assigned_to_lmo_id, task_type: 'field_followup' }
library;

class ScanStatusChangedPayload {
  final String scanId;
  final String newStatus;
  final List<Map<String, dynamic>> ruleResults;
  final String? assignedLmoId;

  const ScanStatusChangedPayload({
    required this.scanId,
    required this.newStatus,
    required this.ruleResults,
    this.assignedLmoId,
  });

  factory ScanStatusChangedPayload.fromJson(Map<String, dynamic> json) {
    final rawRules = json['rule_results'];
    List<Map<String, dynamic>> parsedRules = [];
    if (rawRules is List) {
      parsedRules = rawRules
          .whereType<Map<String, dynamic>>()
          .toList();
    }

    return ScanStatusChangedPayload(
      scanId: json['scan_id']?.toString() ?? '',
      newStatus: json['new_status']?.toString() ?? '',
      ruleResults: parsedRules,
      assignedLmoId: json['assigned_lmo_id']?.toString(),
    );
  }
}

class TaskAssignedPayload {
  final String scanId;
  final String assignedToLmoId;
  final String taskType;

  const TaskAssignedPayload({
    required this.scanId,
    required this.assignedToLmoId,
    this.taskType = 'field_followup',
  });

  factory TaskAssignedPayload.fromJson(Map<String, dynamic> json) {
    return TaskAssignedPayload(
      scanId: json['scan_id']?.toString() ?? '',
      assignedToLmoId: json['assigned_to_lmo_id']?.toString() ?? '',
      taskType: json['task_type']?.toString() ?? 'field_followup',
    );
  }
}

class AppEvent {
  final String id;
  final String eventType;
  final Map<String, dynamic> payload;
  final DateTime createdAt;

  const AppEvent({
    required this.id,
    required this.eventType,
    required this.payload,
    required this.createdAt,
  });

  bool get isScanStatusChanged => eventType == 'scan.status_changed';
  bool get isTaskAssigned => eventType == 'task.assigned';

  ScanStatusChangedPayload? get scanStatusChangedPayload =>
      isScanStatusChanged ? ScanStatusChangedPayload.fromJson(payload) : null;

  TaskAssignedPayload? get taskAssignedPayload =>
      isTaskAssigned ? TaskAssignedPayload.fromJson(payload) : null;

  factory AppEvent.fromJson(Map<String, dynamic> json) {
    DateTime parsedDate;
    try {
      parsedDate = DateTime.parse(json['created_at'].toString()).toUtc();
    } catch (_) {
      parsedDate = DateTime.now().toUtc();
    }

    return AppEvent(
      id: json['id']?.toString() ?? '',
      eventType: json['event_type']?.toString() ?? '',
      payload: (json['payload'] as Map<String, dynamic>?) ?? {},
      createdAt: parsedDate,
    );
  }
}
