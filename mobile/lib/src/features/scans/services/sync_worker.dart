import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:workmanager/workmanager.dart';
import '../../../core/config/app_config.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/database/database_helper.dart';
import '../../auth/data/auth_service.dart';
import '../models/capture_record.dart';
import 'background_sync_dispatcher.dart';

/// Retry budget. Past this a capture stops being retried automatically and is
/// surfaced in the Sync Queue for the officer to deal with by hand.
const int kMaxSyncRetries = 10;

/// Background Synchronization Worker
///
/// Drains the local `captures` queue into POST /scans/ingest. Every upload is
/// authenticated: the backend attributes the scan to the officer who captured
/// it, so an anonymous upload has no evidentiary value and is not attempted.
class SyncWorker extends ChangeNotifier {
  static final SyncWorker _instance = SyncWorker._internal();
  factory SyncWorker() => _instance;

  @visibleForTesting
  factory SyncWorker.createTestInstance({
    DatabaseHelper? dbHelper,
    http.Client? client,
    AuthService? authService,
  }) {
    return SyncWorker._internal(
      dbHelper: dbHelper,
      client: client,
      authService: authService,
    );
  }

  SyncWorker._internal({
    DatabaseHelper? dbHelper,
    http.Client? client,
    AuthService? authService,
  })  : _dbHelper = dbHelper ?? DatabaseHelper(),
        _client = client ?? http.Client(),
        _authService = authService ?? AuthService();

  DatabaseHelper _dbHelper;
  http.Client _client;
  AuthService _authService;
  bool _isSyncing = false;
  String? _lastSyncError;
  final List<String> _stuckPhotos = [];

  bool get isSyncing => _isSyncing;

  /// Human-readable reason the last run could not finish, or null.
  String? get lastSyncError => _lastSyncError;
  List<String> get stuckPhotos => List.unmodifiable(_stuckPhotos);

  @visibleForTesting
  void setDependencies({
    DatabaseHelper? dbHelper,
    http.Client? client,
    AuthService? authService,
  }) {
    if (dbHelper != null) _dbHelper = dbHelper;
    if (client != null) _client = client;
    if (authService != null) _authService = authService;
  }

  /// Initialize OS-level WorkManager for background execution when the app is
  /// killed or backgrounded.
  Future<void> initializeWorkManager() async {
    if (kIsWeb || (!Platform.isAndroid && !Platform.isIOS)) {
      return;
    }

    try {
      await Workmanager().initialize(
        callbackDispatcher,
      );
      await registerPeriodicSync();
      debugPrint('[SyncWorker] WorkManager periodic sync task registered (15 min interval).');
    } catch (e) {
      debugPrint('[SyncWorker] WorkManager initialization note: $e');
    }
  }

  /// (Re-)register the recurring upload job. Called again when the officer
  /// flips the Wi-Fi-only preference, so the constraint actually takes effect
  /// rather than only changing a label in Settings.
  Future<void> registerPeriodicSync() async {
    if (kIsWeb || (!Platform.isAndroid && !Platform.isIOS)) {
      return;
    }
    try {
      await Workmanager().registerPeriodicTask(
        kPeriodicSyncTaskName,
        kPeriodicSyncTaskName,
        frequency: const Duration(minutes: 15),
        constraints: Constraints(
          networkType: AppConfig().wifiOnlySync ? NetworkType.unmetered : NetworkType.connected,
        ),
        existingWorkPolicy: ExistingPeriodicWorkPolicy.replace,
      );
    } catch (e) {
      debugPrint('[SyncWorker] Periodic task registration: $e');
    }
  }

  /// Schedule a one-off background task when a new capture occurs while offline
  Future<void> scheduleOneOffSync() async {
    if (kIsWeb || (!Platform.isAndroid && !Platform.isIOS)) {
      return;
    }

    try {
      await Workmanager().registerOneOffTask(
        'sync_${DateTime.now().millisecondsSinceEpoch}',
        kBackgroundSyncTaskName,
        constraints: Constraints(
          networkType: AppConfig().wifiOnlySync ? NetworkType.unmetered : NetworkType.connected,
        ),
      );
    } catch (e) {
      debugPrint('[SyncWorker] One-off task registration: $e');
    }
  }

  /// Re-queue anything left mid-upload by a crash or force-stop.
  Future<int> recoverOrphanedUploads() async {
    try {
      final recovered = await _dbHelper.recoverOrphanedUploads();
      if (recovered > 0) {
        debugPrint('[SyncWorker] Recovered $recovered capture(s) orphaned in UPLOADING.');
        notifyListeners();
      }
      return recovered;
    } catch (e) {
      debugPrint('[SyncWorker] Orphan recovery failed: $e');
      return 0;
    }
  }

  /// Execute one batch synchronization pass. Returns the number uploaded.
  Future<int> syncPendingCaptures() async {
    if (_isSyncing) return 0;

    _isSyncing = true;
    _lastSyncError = null;
    notifyListeners();

    int syncedCount = 0;

    try {
      final token = _authService.currentToken?.accessToken;
      if (token == null || token.isEmpty) {
        // Nothing is lost: captures stay queued until the officer signs in.
        _lastSyncError = 'Sign in to upload your captures.';
        debugPrint('[SyncWorker] No session; leaving queue untouched.');
        return 0;
      }

      final batch = await _dbHelper.getPendingOrFailedCaptures(limit: 10);
      debugPrint('[SyncWorker] Found ${batch.length} capture(s) due for upload.');

      for (final capture in batch) {
        // An evidence file that is gone cannot be re-created, and uploading a
        // placeholder would attach a hash to bytes that were never photographed.
        final imageBytes = await _readEvidenceBytes(capture);
        if (imageBytes == null) {
          await _markUnrecoverable(
            capture,
            'The photo for this capture is missing from device storage and cannot be uploaded. Discard it and re-inspect.',
          );
          continue;
        }

        await _dbHelper.updateSyncStatus(capture.localId, 'UPLOADING');
        notifyListeners();

        try {
          final uri = Uri.parse(ApiConstants.scansIngestEndpoint);
          final request = http.MultipartRequest('POST', uri);
          request.headers.addAll(_authService.authHeaders);

          if (capture.lat != null) {
            request.fields['lat'] = capture.lat.toString();
          }
          if (capture.lng != null) {
            request.fields['lng'] = capture.lng.toString();
          }
          request.fields['captured_at_utc'] = capture.capturedAtUtc;
          request.fields['reference_object_type'] = capture.referenceObjectType;
          request.fields['product_type'] = capture.productType;
          if (capture.productName != null && capture.productName!.trim().isNotEmpty) {
            request.fields['product_name'] = capture.productName!.trim();
          }
          request.fields['source'] = 'mobile';
          // Stable per-install id: the Section 65B hash is computed over it, so
          // it must match what was used when the capture was taken.
          request.fields['device_id'] = capture.deviceId ?? AppConfig().deviceId;

          request.files.add(
            http.MultipartFile.fromBytes(
              'image',
              imageBytes,
              filename: 'capture_${capture.localId}.jpg',
              contentType: MediaType('image', 'jpeg'),
            ),
          );

          final streamedResponse = await _client.send(request).timeout(const Duration(seconds: 30));
          final response = await http.Response.fromStream(streamedResponse);

          if (response.statusCode == 201 || response.statusCode == 200) {
            final Map<String, dynamic> responseData =
                jsonDecode(response.body) as Map<String, dynamic>;
            final serverScanId = responseData['scan_id']?.toString() ?? 'ACK-${capture.localId}';

            await _dbHelper.markSyncedAndCleanLocalImage(
              localId: capture.localId,
              imagePath: capture.imagePath,
              serverScanId: serverScanId,
            );

            syncedCount++;
            debugPrint('[SyncWorker] Capture ${capture.localId} synced -> $serverScanId');
          } else if (response.statusCode == 401) {
            // The token died mid-shift. Stop the run rather than burning the
            // retry budget of every queued capture on a doomed request.
            await _dbHelper.updateSyncStatus(
              capture.localId,
              'PENDING_UPLOAD',
              lastError: 'Session expired before upload.',
              clearBackoff: true,
            );
            _lastSyncError = 'Your session expired. Sign in again to resume uploading.';
            await _authService.handleUnauthorized();
            return syncedCount;
          } else if (response.statusCode == 413) {
            await _markUnrecoverable(
              capture,
              'The server rejected this photo as too large. Discard it and re-capture.',
            );
            continue;
          } else {
            throw Exception('Server rejected upload with HTTP ${response.statusCode}: ${response.body}');
          }
        } on SocketException catch (e) {
          await _handleSyncFailure(capture, 'No connection to the server (${e.message}).');
        } on http.ClientException catch (e) {
          await _handleSyncFailure(capture, 'Connection to the server failed (${e.message}).');
        } on TimeoutException catch (_) {
          await _handleSyncFailure(capture, 'Upload timed out after 30 seconds.');
        } catch (e) {
          await _handleSyncFailure(capture, e.toString());
        }

        notifyListeners();
      }
    } finally {
      _isSyncing = false;
      notifyListeners();
    }

    return syncedCount;
  }

  /// Read the queued photo, or null when there is nothing real to upload.
  Future<Uint8List?> _readEvidenceBytes(CaptureRecord capture) async {
    final path = capture.imagePath;
    if (path == null || path.isEmpty) return null;
    try {
      final file = File(path);
      if (!file.existsSync()) return null;
      final bytes = await file.readAsBytes();
      // A JPEG header alone is the placeholder the old simulator path wrote.
      // Anything that small is not a photograph of a package.
      if (bytes.length < 1024) return null;
      return bytes;
    } catch (e) {
      debugPrint('[SyncWorker] Could not read evidence file for ${capture.localId}: $e');
      return null;
    }
  }

  /// Park a capture that retrying cannot fix, so it stops consuming the queue
  /// but stays visible for the officer to discard deliberately.
  Future<void> _markUnrecoverable(CaptureRecord capture, String reason) async {
    _lastSyncError = reason;
    if (!_stuckPhotos.contains(capture.localId)) {
      _stuckPhotos.add(capture.localId);
    }
    await _dbHelper.updateSyncStatus(
      capture.localId,
      'FAILED',
      retryCount: kMaxSyncRetries + 1,
      lastError: reason,
      clearBackoff: true,
    );
    debugPrint('[SyncWorker] ${capture.localId} parked: $reason');
    notifyListeners();
  }

  Future<void> _handleSyncFailure(CaptureRecord capture, String errorMsg) async {
    _lastSyncError = errorMsg;
    final nextRetry = capture.retryCount + 1;

    await _dbHelper.updateSyncStatus(
      capture.localId,
      'FAILED',
      retryCount: nextRetry,
      lastError: errorMsg,
      nextAttemptAt: DateTime.now().toUtc().add(backoffDelay(nextRetry)),
    );

    if (nextRetry > kMaxSyncRetries) {
      if (!_stuckPhotos.contains(capture.localId)) {
        _stuckPhotos.add(capture.localId);
      }
      debugPrint('[SyncWorker] ALERT: Photo ${capture.localId} stuck after $nextRetry retries.');
    }
  }

  /// Exponential backoff, capped at 30 minutes: 30s, 1m, 2m, 4m ... so a long
  /// stretch out of coverage does not exhaust the retry budget before the
  /// officer is back on a network.
  @visibleForTesting
  static Duration backoffDelay(int retryCount) {
    final exponent = math.min(retryCount - 1, 6);
    final seconds = 30 * math.pow(2, exponent < 0 ? 0 : exponent).toInt();
    return Duration(seconds: math.min(seconds, 1800));
  }
}
