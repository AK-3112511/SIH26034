import 'package:flutter/foundation.dart';
import 'package:workmanager/workmanager.dart';
import 'sync_worker.dart';

const String kBackgroundSyncTaskName = 'com.metrologyai.mobile.background_sync';
const String kPeriodicSyncTaskName = 'com.metrologyai.mobile.periodic_sync';

/// Top-level Callback Dispatcher for Android WorkManager
/// Invoked headless by Android OS when network connectivity is restored or 15-min timer triggers.
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((taskName, inputData) async {
    debugPrint('[WorkManager] Headless task started: $taskName');

    try {
      final syncWorker = SyncWorker();
      final syncedCount = await syncWorker.syncPendingCaptures();
      debugPrint('[WorkManager] Successfully synced $syncedCount capture(s) in background.');
      return Future.value(true);
    } catch (e, stack) {
      debugPrint('[WorkManager] Background sync execution failed: $e\n$stack');
      return Future.value(false);
    }
  });
}
