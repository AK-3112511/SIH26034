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
}

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

  static List<NotificationItem> mockNotifications() {
    final now = DateTime.now();
    return [
      NotificationItem(
        id: 'notif-001',
        title: 'Compliance Verdict: Failed',
        body: 'Your scan at Reliance Retail (Coimbatore) was marked Failed — Rule 6(1)(e) Net Qty Font Violation (1.2mm < 3.0mm mandated).',
        category: NotificationCategory.compliance,
        timestamp: now.subtract(const Duration(minutes: 12)),
        isRead: false,
      ),
      NotificationItem(
        id: 'notif-002',
        title: 'Sync Queue: 3 Scans Ingested',
        body: '3 offline captures in your local queue synced successfully to the central repository. Section 65B hashes validated.',
        category: NotificationCategory.syncEvent,
        timestamp: now.subtract(const Duration(hours: 1, minutes: 4)),
        isRead: false,
        deepLinkRoute: '/sync-queue',
      ),
      NotificationItem(
        id: 'notif-003',
        title: 'Queue Alert: Photo Stuck',
        body: 'Capture #LOC-88FE exceeded 10 upload retries (§3.1). Background sync suspended. Please check in Sync Queue.',
        category: NotificationCategory.stuckAlert,
        timestamp: now.subtract(const Duration(hours: 3)),
        isRead: false,
        deepLinkRoute: '/sync-queue',
      ),
      NotificationItem(
        id: 'notif-004',
        title: 'Section 39 Challan Dispatched',
        body: 'Legal Notice & Form 4 Notice generated for Scan #4C8E7456 against Manufacturer M/s Britannia Industries.',
        category: NotificationCategory.challanNotice,
        timestamp: now.subtract(const Duration(days: 1)),
        isRead: true,
      ),
      NotificationItem(
        id: 'notif-005',
        title: 'PCR 2011 Schedule II Ruleset Active',
        body: 'MetrologyAI Engine updated ruleset version to v2.4. Effective for all Tamil Nadu field inspections.',
        category: NotificationCategory.systemUpdate,
        timestamp: now.subtract(const Duration(days: 2)),
        isRead: true,
      ),
    ];
  }
}
