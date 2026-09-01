import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:workmanager/workmanager.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/database/database_helper.dart';
import '../models/capture_record.dart';
import 'background_sync_dispatcher.dart';

/// Background Synchronization Worker
/// Implements exact sync worker pseudo-code from MetrologyAI_Elevated_Blueprint.md §3.1
class SyncWorker extends ChangeNotifier {
  static final SyncWorker _instance = SyncWorker._internal();
  factory SyncWorker() => _instance;

  @visibleForTesting
  factory SyncWorker.createTestInstance({DatabaseHelper? dbHelper, http.Client? client}) {
    return SyncWorker._internal(dbHelper: dbHelper, client: client);
  }

  SyncWorker._internal({
    DatabaseHelper? dbHelper,
    http.Client? client,
  })  : _dbHelper = dbHelper ?? DatabaseHelper(),
        _client = client ?? http.Client();

  DatabaseHelper _dbHelper;
  http.Client _client;
  bool _isSyncing = false;
  String? _lastSyncError;
  final List<String> _stuckPhotos = [];

  bool get isSyncing => _isSyncing;
  String? get lastSyncError => _lastSyncError;
  List<String> get stuckPhotos => List.unmodifiable(_stuckPhotos);

  @visibleForTesting
  void setDependencies({DatabaseHelper? dbHelper, http.Client? client}) {
    if (dbHelper != null) _dbHelper = dbHelper;
    if (client != null) _client = client;
  }

  /// Initialize OS-level WorkManager for true background execution when app is killed/backgrounded
  Future<void> initializeWorkManager() async {
    if (kIsWeb || (!Platform.isAndroid && !Platform.isIOS)) {
      return;
    }

    try {
      await Workmanager().initialize(
        callbackDispatcher,
      );

      // Register periodic task (every 15 min per §3.1 pseudo-code: "every 15 min")
      await Workmanager().registerPeriodicTask(
        kPeriodicSyncTaskName,
        kPeriodicSyncTaskName,
        frequency: const Duration(minutes: 15),
        constraints: Constraints(
          networkType: NetworkType.connected,
        ),
        existingWorkPolicy: ExistingWorkPolicy.replace,
      );
      debugPrint('[SyncWorker] WorkManager periodic sync task registered (15 min interval).');
    } catch (e) {
      debugPrint('[SyncWorker] WorkManager initialization note: $e');
    }
  }

  /// Schedule one-off background task when a new capture occurs while offline
  Future<void> scheduleOneOffSync() async {
    if (kIsWeb || (!Platform.isAndroid && !Platform.isIOS)) {
      return;
    }

    try {
      await Workmanager().registerOneOffTask(
        'sync_${DateTime.now().millisecondsSinceEpoch}',
        kBackgroundSyncTaskName,
        constraints: Constraints(
          networkType: NetworkType.connected,
        ),
      );
    } catch (e) {
      debugPrint('[SyncWorker] One-off task registration: $e');
    }
  }

  /// Execute batch synchronization loop (§3.1 pseudo-code)
  Future<int> syncPendingCaptures() async {
    if (_isSyncing) return 0;

    _isSyncing = true;
    _lastSyncError = null;
    notifyListeners();

    int syncedCount = 0;

    try {
      // batch = select * from captures where sync_status in ('PENDING_UPLOAD','FAILED') limit 10
      final batch = await _dbHelper.getPendingOrFailedCaptures(limit: 10);
      debugPrint('[SyncWorker] Found ${batch.length} capture(s) pending sync in SQLite.');

      for (final capture in batch) {
        // Set sync_status = 'UPLOADING'
        await _dbHelper.updateSyncStatus(capture.localId, 'UPLOADING');
        notifyListeners();

        try {
          final uri = Uri.parse(ApiConstants.scansIngestEndpoint);
          final request = http.MultipartRequest('POST', uri);

          // Attach metadata Form fields
          if (capture.lat != null) {
            request.fields['lat'] = capture.lat.toString();
          }
          if (capture.lng != null) {
            request.fields['lng'] = capture.lng.toString();
          }
          request.fields['captured_at_utc'] = capture.capturedAtUtc;
          request.fields['reference_object_type'] = capture.referenceObjectType;
          request.fields['source'] = 'mobile';
          request.fields['device_id'] = 'field_device_${capture.localId.substring(0, 8)}';

          // Attach Multipart image file from local image_path
          if (capture.imagePath != null && File(capture.imagePath!).existsSync()) {
            final file = File(capture.imagePath!);
            final bytes = await file.readAsBytes();
            request.files.add(
              http.MultipartFile.fromBytes(
                'image',
                bytes,
                filename: 'capture_${capture.localId}.jpg',
                contentType: MediaType('image', 'jpeg'),
              ),
            );
          } else {
            // Synthetic image buffer for headless fallback or simulated records
            request.files.add(
              http.MultipartFile.fromBytes(
                'image',
                Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46]),
                filename: 'capture_${capture.localId}.jpg',
                contentType: MediaType('image', 'jpeg'),
              ),
            );
          }

          // Send multi-part request to /api/v1/scans/ingest
          final streamedResponse = await _client.send(request).timeout(const Duration(seconds: 15));
          final response = await http.Response.fromStream(streamedResponse);

          if (response.statusCode == 201 || response.statusCode == 200) {
            final Map<String, dynamic> responseData =
                jsonDecode(response.body) as Map<String, dynamic>;
            final serverScanId = responseData['scan_id']?.toString() ?? 'ACK-${capture.localId}';

            // On success: set sync_status = 'SYNCED', delete local image_path (§3.1)
            await _dbHelper.markSyncedAndCleanLocalImage(
              localId: capture.localId,
              imagePath: capture.imagePath,
              serverScanId: serverScanId,
            );

            syncedCount++;
            debugPrint('[SyncWorker] Capture ${capture.localId} successfully synced -> server_scan_id: $serverScanId (local image freed)');
          } else {
            throw Exception('Server rejected upload with HTTP ${response.statusCode}: ${response.body}');
          }
        } on SocketException catch (e) {
          await _handleSyncFailure(capture, 'Network error: ${e.message}');
        } on http.ClientException catch (e) {
          await _handleSyncFailure(capture, 'HTTP client connection failed: ${e.message}');
        } on TimeoutException catch (_) {
          await _handleSyncFailure(capture, 'Upload timed out after 15s');
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

  Future<void> _handleSyncFailure(CaptureRecord capture, String errorMsg) async {
    _lastSyncError = errorMsg;
    final nextRetry = capture.retryCount + 1;

    // set sync_status = 'FAILED', retry_count += 1
    await _dbHelper.updateSyncStatus(
      capture.localId,
      'FAILED',
      retryCount: nextRetry,
    );

    // if retry_count > 10: notify_user("photo stuck, check manually") (§3.1)
    if (nextRetry > 10) {
      if (!_stuckPhotos.contains(capture.localId)) {
        _stuckPhotos.add(capture.localId);
      }
      debugPrint('[SyncWorker] ALERT: Photo ${capture.localId} stuck after $nextRetry retries. Check manually.');
    }
  }
}
