import 'package:flutter/material.dart';
import '../../../core/theme/design_tokens.dart';

enum NotificationCategory {
  compliance('Compliance', Icons.gavel_outlined, AppColors.verdictFail),
  syncEvent('Sync Event', Icons.cloud_sync_outlined, AppColors.brass500),
  stuckAlert('Queue Alert', Icons.warning_amber_rounded, AppColors.verdictPending),
  challanNotice('Legal Notice', Icons.receipt_long_outlined, AppColors.ink900),
  systemUpdate('System', Icons.info_outline, AppColors.ink600);

  final String label;
  final IconData icon;
  final Color color;
  const NotificationCategory(this.label, this.icon, this.color);

  static NotificationCategory fromName(String? name) {
    return NotificationCategory.values.firstWhere(
      (c) => c.name == name,
      orElse: () => NotificationCategory.systemUpdate,
    );
  }
}

/// One entry in the in-app alerts feed, persisted in the `notifications` table
/// so an alert raised by the headless background isolate is still there when
/// the officer next opens the app.
class NotificationItem {
  final String id;
  final String title;
  final String body;
  final NotificationCategory category;
  final DateTime timestamp;
  bool isRead;
  final String? deepLinkRoute;

  NotificationItem({
    required this.id,
    required this.title,
    required this.body,
    required this.category,
    required this.timestamp,
    this.isRead = false,
    this.deepLinkRoute,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'title': title,
      'body': body,
      'category': category.name,
      'timestamp_utc': timestamp.toUtc().toIso8601String(),
      'is_read': isRead ? 1 : 0,
      'deep_link_route': deepLinkRoute,
    };
  }

  factory NotificationItem.fromMap(Map<String, dynamic> map) {
    return NotificationItem(
      id: map['id'] as String,
      title: map['title'] as String? ?? '',
      body: map['body'] as String? ?? '',
      category: NotificationCategory.fromName(map['category'] as String?),
      timestamp:
          DateTime.tryParse(map['timestamp_utc'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      isRead: (map['is_read'] as num?)?.toInt() == 1,
      deepLinkRoute: map['deep_link_route'] as String?,
    );
  }
}
