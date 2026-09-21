import 'package:flutter/foundation.dart';
import 'package:workmanager/workmanager.dart';
import '../../notifications/services/event_polling_service.dart';
import '../../notifications/services/notification_service.dart';
import 'sync_worker.dart';

const String kBackgroundSyncTaskName = 'com.metrologyai.mobile.background_sync';
const String kPeriodicSyncTaskName = 'com.metrologyai.mobile.periodic_sync';

/// Top-level Callback Dispatcher for Android WorkManager
/// Invoked headless by Android OS when network connectivity is restored or 15-min timer triggers.
/// Handles both offline capture syncing (§3.1) and background push notification delivery (§5.2).
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((taskName, inputData) async {
    debugPrint('[WorkManager] Headless background task started: $taskName');

    try {
      // 1. Synchronize offline captures (§3.1)
      final syncWorker = SyncWorker();
      final syncedCount = await syncWorker.syncPendingCaptures();
      debugPrint('[WorkManager] Successfully synced $syncedCount capture(s) in background.');

      // 2. Poll real-time event layer for status changes and assigned tasks (§5.2 & §6.2)
      final eventPolling = EventPollingService();
      final newEvents = await eventPolling.pollOnce();
      if (newEvents.isNotEmpty) {
        final notifService = NotificationService();
        for (final event in newEvents) {
          await notifService.handleEvent(event);
        }
        debugPrint('[WorkManager] Processed ${newEvents.length} event(s) and fired lockscreen notification(s).');
      }

      return Future.value(true);
    } catch (e, stack) {
      debugPrint('[WorkManager] Background task execution failed: $e\n$stack');
      return Future.value(false);
    }
  });
}

