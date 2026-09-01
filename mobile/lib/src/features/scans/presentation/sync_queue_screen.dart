import 'dart:io';
import 'package:flutter/material.dart';
import '../../../core/database/database_helper.dart';
import '../../../core/theme/design_tokens.dart';
import '../../../core/widgets/calibration_tick_rule.dart';
import '../../../core/widgets/status_chip.dart';
import '../models/capture_record.dart';
import '../services/sync_worker.dart';

/// Sync Queue Screen (Mobile UX §2, Screen 6)
///
/// Visibility into the local offline SQLite queue.
/// Displays PENDING_UPLOAD, FAILED, and STUCK (retry_count > 10) captures
/// with disk storage usage metrics and manual retry controls.
class SyncQueueScreen extends StatefulWidget {
  final List<CaptureRecord>? initialCaptures;
  final DatabaseHelper? databaseHelper;
  final SyncWorker? syncWorker;

  const SyncQueueScreen({
    super.key,
    this.initialCaptures,
    this.databaseHelper,
    this.syncWorker,
  });

  @override
  State<SyncQueueScreen> createState() => _SyncQueueScreenState();
}

class _SyncQueueScreenState extends State<SyncQueueScreen> {
  late final DatabaseHelper _dbHelper;
  late final SyncWorker _syncWorker;

  List<CaptureRecord> _unsyncedCaptures = [];
  int _totalStorageBytes = 0;

  @override
  void initState() {
    super.initState();
    _dbHelper = widget.databaseHelper ?? DatabaseHelper();
    _syncWorker = widget.syncWorker ?? SyncWorker();
    _syncWorker.addListener(_onSyncUpdate);

    if (widget.initialCaptures != null) {
      _unsyncedCaptures = List.from(widget.initialCaptures!);
    } else {
      _loadQueue();
    }
  }

  @override
  void dispose() {
    _syncWorker.removeListener(_onSyncUpdate);
    super.dispose();
  }

  void _onSyncUpdate() {
    if (mounted) {
      _loadQueue();
    }
  }

  Future<void> _loadQueue() async {
    try {
      final records = await _dbHelper.getUnsyncedCaptures();

      int bytes = 0;
      for (final r in records) {
        if (r.imagePath != null && r.imagePath!.isNotEmpty) {
          try {
            final file = File(r.imagePath!);
            if (file.existsSync()) {
              bytes += file.lengthSync();
            }
          } catch (_) {}
        }
      }

      if (!mounted) return;
      setState(() {
        _unsyncedCaptures = records;
        _totalStorageBytes = bytes;
      });
    } catch (e) {
      debugPrint('Error loading sync queue: $e');
    }
  }

  String _formatStorageSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }

  Future<void> _handleRetryAll() async {
    final count = await _syncWorker.syncPendingCaptures();
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: AppColors.ink900,
        content: Row(
          children: [
            const Icon(Icons.sync, color: AppColors.brass500, size: 20),
            const SizedBox(width: AppSpacing.space1),
            Expanded(
              child: Text(
                count > 0
                    ? 'Sync complete: $count item(s) uploaded.'
                    : (_syncWorker.lastSyncError ?? 'Queue sync attempted.'),
                style: AppTypography.xs.copyWith(color: AppColors.paper000),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _handleForceRetry(CaptureRecord record) async {
    _dbHelper.resetCaptureRetry(record.localId).then((_) {
      _syncWorker.syncPendingCaptures();
      if (mounted) _loadQueue();
    });
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: AppColors.ink900,
        content: Text(
          'Force sync triggered for ${record.localId.substring(0, 8).toUpperCase()}',
          style: AppTypography.xs.copyWith(color: AppColors.paper000),
        ),
      ),
    );
  }

  Future<void> _handleDiscard(CaptureRecord record) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.paper000,
        title: const Text('Discard Stuck Capture?', style: AppTypography.lg),
        content: Text(
          'Are you sure you want to discard capture #${record.localId.substring(0, 8).toUpperCase()}? The local evidence photo will be deleted.',
          style: AppTypography.xs.copyWith(color: AppColors.ink900),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('CANCEL'),
          ),
          ElevatedButton(
            key: const Key('confirm_discard_dialog_btn'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.verdictFail,
              foregroundColor: AppColors.paper000,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('DISCARD'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      if (mounted) {
        setState(() {
          _unsyncedCaptures.removeWhere((c) => c.localId == record.localId);
        });
      }
      _dbHelper.deleteCapture(record.localId, record.imagePath).then((_) {
        if (mounted) _loadQueue();
      });
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.ink900,
          duration: const Duration(seconds: 1),
          content: Text(
            'Capture #${record.localId.substring(0, 8).toUpperCase()} discarded.',
            style: AppTypography.xs.copyWith(color: AppColors.paper000),
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.paper100,
      appBar: AppBar(
        title: const Text('Offline Sync Queue'),
        actions: [
          IconButton(
            tooltip: 'Refresh Queue',
            icon: const Icon(Icons.refresh, color: AppColors.paper000),
            onPressed: _loadQueue,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
                  // Storage & Queue Summary Header Card
                  Padding(
                    padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
                    child: Card(
                      margin: EdgeInsets.zero,
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.space2),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(
                                  Icons.storage_outlined,
                                  color: AppColors.brass500,
                                  size: 20.0,
                                ),
                                const SizedBox(width: AppSpacing.space1),
                                Text(
                                  'LOCAL STORAGE & QUEUE FOOTPRINT',
                                  style: AppTypography.xs.copyWith(
                                    color: AppColors.ink600,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: AppSpacing.space1),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _formatStorageSize(_totalStorageBytes),
                                      style: AppTypography.xl.copyWith(
                                        color: AppColors.ink900,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    Text(
                                      '${_unsyncedCaptures.length} local capture(s) pending',
                                      style: AppTypography.xs.copyWith(color: AppColors.ink600),
                                    ),
                                  ],
                                ),
                                if (_unsyncedCaptures.isNotEmpty)
                                  ElevatedButton.icon(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: AppColors.brass500,
                                      foregroundColor: AppColors.paper000,
                                      minimumSize: const Size(130, 42),
                                    ),
                                    icon: _syncWorker.isSyncing
                                        ? const SizedBox(
                                            width: 14,
                                            height: 14,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                              color: AppColors.paper000,
                                            ),
                                          )
                                        : const Icon(Icons.cloud_upload_outlined, size: 16),
                                    label: Text(
                                      _syncWorker.isSyncing ? 'SYNCING...' : 'RETRY ALL',
                                      style: AppTypography.xs.copyWith(
                                        fontWeight: FontWeight.bold,
                                        color: AppColors.paper000,
                                      ),
                                    ),
                                    onPressed: _syncWorker.isSyncing ? null : _handleRetryAll,
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),

                  // Divider
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: AppConstraints.mobileScreenMargin),
                    child: CalibrationTickRule(),
                  ),

                  // Main List Area
                  Expanded(
                    child: _unsyncedCaptures.isEmpty
                        ? _buildEmptyState()
                        : ListView.separated(
                            padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
                            itemCount: _unsyncedCaptures.length,
                            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.space2),
                            itemBuilder: (context, index) {
                              final record = _unsyncedCaptures[index];
                              final isStuck = record.retryCount > 10;

                              return isStuck
                                  ? _buildStuckCard(record)
                                  : _buildRegularQueueCard(record);
                            },
                          ),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.space4),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 56.0,
              height: 56.0,
              decoration: BoxDecoration(
                color: AppColors.verdictPass.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.cloud_done_outlined,
                color: AppColors.verdictPass,
                size: 32.0,
              ),
            ),
            const SizedBox(height: AppSpacing.space2),
            const Text(
              'Offline Queue is Empty',
              style: AppTypography.lg,
            ),
            const SizedBox(height: AppSpacing.space1),
            Text(
              'All field captures have been verified and synced with the central repository. Local image storage has been freed.',
              textAlign: TextAlign.center,
              style: AppTypography.xs.copyWith(color: AppColors.ink600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRegularQueueCard(CaptureRecord record) {
    final localIdShort = record.localId.substring(0, 8).toUpperCase();
    final isUploading = record.syncStatus.toUpperCase() == 'UPLOADING';

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.space2),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.inventory_2_outlined,
                      color: AppColors.brass500,
                      size: 18.0,
                    ),
                    const SizedBox(width: AppSpacing.space1),
                    Text(
                      'CAPTURE #$localIdShort',
                      style: AppTypography.base.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppColors.ink900,
                      ),
                    ),
                  ],
                ),
                StatusChip(status: record.toUiSyncStatus),
              ],
            ),
            const SizedBox(height: AppSpacing.space1),
            Text(
              'Type: ${record.referenceObjectType.toUpperCase()} • Captured: ${record.capturedAtUtc.substring(11, 16)} UTC',
              style: AppTypography.xs.copyWith(color: AppColors.ink600),
            ),
            const SizedBox(height: AppSpacing.space1),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  record.retryCount > 0
                      ? 'Auto-retry count: ${record.retryCount}/10'
                      : 'Pending initial upload',
                  style: AppTypography.dataMono.copyWith(
                    fontSize: 11.0,
                    color: record.retryCount > 0 ? AppColors.verdictPending : AppColors.ink600,
                  ),
                ),
                TextButton.icon(
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    foregroundColor: AppColors.ink900,
                  ),
                  icon: isUploading
                      ? const SizedBox(
                          width: 12,
                          height: 12,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.replay, size: 14),
                  label: Text(
                    isUploading ? 'UPLOADING...' : 'RETRY NOW',
                    style: AppTypography.xs.copyWith(fontWeight: FontWeight.bold),
                  ),
                  onPressed: isUploading ? null : () => _handleForceRetry(record),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// Distinct Stuck Capture Card (§3.1: retry_count > 10 notify_user("photo stuck, check manually"))
  Widget _buildStuckCard(CaptureRecord record) {
    final localIdShort = record.localId.substring(0, 8).toUpperCase();

    return Container(
      decoration: BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(
          color: AppColors.verdictPending,
          width: 1.5,
        ),
      ),
      padding: const EdgeInsets.all(AppSpacing.space2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(
                    Icons.warning_amber_rounded,
                    color: AppColors.verdictPending,
                    size: 20.0,
                  ),
                  const SizedBox(width: AppSpacing.space1),
                  Text(
                    'CAPTURE #$localIdShort',
                    style: AppTypography.base.copyWith(
                      fontWeight: FontWeight.bold,
                      color: AppColors.ink900,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.verdictPending.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(AppRadius.sealBadge),
                  border: Border.all(color: AppColors.verdictPending),
                ),
                child: Text(
                  'STUCK (10+ RETRIES)',
                  style: AppTypography.xs.copyWith(
                    fontWeight: FontWeight.bold,
                    color: AppColors.verdictPending,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.space1),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.space1),
            decoration: BoxDecoration(
              color: AppColors.paper100,
              borderRadius: BorderRadius.circular(AppRadius.card),
            ),
            child: Text(
              '⚠️ Automatic background sync suspended (§3.1). Upload failed 10+ times. File may be damaged or rejected by server.',
              style: AppTypography.xs.copyWith(
                color: AppColors.ink900,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.space1),
          Text(
            'Target Type: ${record.referenceObjectType.toUpperCase()} • Retries: ${record.retryCount}',
            style: AppTypography.xs.copyWith(color: AppColors.ink600),
          ),
          const SizedBox(height: AppSpacing.space1),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              OutlinedButton.icon(
                key: Key('stuck_discard_btn_${record.localId}'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.verdictFail,
                  side: const BorderSide(color: AppColors.verdictFail),
                  minimumSize: const Size(90, 36),
                ),
                icon: const Icon(Icons.delete_outline, size: 14),
                label: const Text('DISCARD'),
                onPressed: () => _handleDiscard(record),
              ),
              const SizedBox(width: AppSpacing.space1),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.ink900,
                  foregroundColor: AppColors.paper000,
                  minimumSize: const Size(120, 36),
                ),
                icon: const Icon(Icons.refresh, size: 14),
                label: const Text('FORCE RETRY'),
                onPressed: () => _handleForceRetry(record),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
