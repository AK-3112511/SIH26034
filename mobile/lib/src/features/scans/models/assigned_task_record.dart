/// Model representing an assigned field task persisted in SQLite per §5.3
class AssignedTaskRecord {
  final String scanId;
  final String title;
  final String category;
  final String platform;
  final String location;
  final String assignedAtUtc;
  final String taskType;
  final String status;
  final String instructions;

  const AssignedTaskRecord({
    required this.scanId,
    required this.title,
    required this.category,
    required this.platform,
    required this.location,
    required this.assignedAtUtc,
    this.taskType = 'field_followup',
    this.status = 'PENDING',
    this.instructions = '',
  });

  Map<String, dynamic> toMap() {
    return {
      'scan_id': scanId,
      'title': title,
      'category': category,
      'platform': platform,
      'location': location,
      'assigned_at_utc': assignedAtUtc,
      'task_type': taskType,
      'status': status,
      'instructions': instructions,
    };
  }

  factory AssignedTaskRecord.fromMap(Map<String, dynamic> map) {
    return AssignedTaskRecord(
      scanId: map['scan_id'] as String? ?? '',
      title: map['title'] as String? ?? 'E-Commerce Package',
      category: map['category'] as String? ?? 'E-Commerce Follow-up',
      platform: map['platform'] as String? ?? 'E-Commerce',
      location: map['location'] as String? ?? 'Seller Verification Site',
      assignedAtUtc: map['assigned_at_utc'] as String? ??
          DateTime.now().toUtc().toIso8601String(),
      taskType: map['task_type'] as String? ?? 'field_followup',
      status: map['status'] as String? ?? 'PENDING',
      instructions: map['instructions'] as String? ?? '',
    );
  }
}
