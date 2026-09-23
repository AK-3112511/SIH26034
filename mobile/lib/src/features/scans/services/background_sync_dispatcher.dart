import 'package:flutter/widgets.dart';
import 'package:workmanager/workmanager.dart';
import '../../../core/config/app_config.dart';
import '../../auth/data/auth_service.dart';
import '../../notifications/services/event_polling_service.dart';
import '../../notifications/services/local_notification_service.dart';
import '../../notifications/services/notification_service.dart';
import 'sync_worker.dart';

const String kBackgroundSyncTaskName = 'com.metrologyai.mobile.background_sync';
const String kPeriodicSyncTaskName = 'com.metrologyai.mobile.periodic_sync';

/// Top-level callback dispatcher for Android WorkManager.
///
/// Runs headless in its own isolate, so nothing the UI set up is available
/// here: the server address, the stored JWT and the notification channel all
/// have to be re-established before any network call. Skipping that is why
/// background sync previously uploaded nothing and polled unauthenticated.
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((taskName, inputData) async {
    WidgetsFlutterBinding.ensureInitialized();
    debugPrint('[WorkManager] Headless background task started: $taskName');

    try {
      // 1. Restore this isolate's context: server URL + device id, then the
      //    persisted session. Without a token every request below is a 401.
      await AppConfig().load();
      await AuthService().loadStoredToken();
      if (!AuthService().isAuthenticated) {
        debugPrint('[WorkManager] No stored session; deferring until next sign-in.');
        return Future.value(true);
      }
      await LocalNotificationService().initialize();

      // 2. Upload queued captures, recovering anything a previous run left
      //    stranded mid-upload.
      final syncWorker = SyncWorker();
      await syncWorker.recoverOrphanedUploads();
      final syncedCount = await syncWorker.syncPendingCaptures();
      debugPrint('[WorkManager] Synced $syncedCount capture(s) in background.');

      // 3. Poll the event layer so a verdict reached while the app was closed
      //    still reaches the lock screen.
      final eventPolling = EventPollingService();
      final newEvents = await eventPolling.pollOnce();
      if (newEvents.isNotEmpty) {
        final notifService = NotificationService();
        await notifService.loadPersisted();
        for (final event in newEvents) {
          await notifService.handleEvent(event);
        }
        debugPrint('[WorkManager] Processed ${newEvents.length} event(s).');
      }

      return Future.value(true);
    } catch (e, stack) {
      debugPrint('[WorkManager] Background task execution failed: $e\n$stack');
      return Future.value(false);
    }
  });
}
