import 'package:flutter/material.dart';

import '../../../core/database/database_helper.dart';
import '../../../core/theme/design_tokens.dart';
import '../../../core/widgets/status_chip.dart';
import '../../../core/widgets/verdict_seal_badge.dart';
import '../models/capture_record.dart';
import '../services/verdict_sync_service.dart';

/// Human wording for the rule ids the backend reports, so a field officer is
/// not asked to decode "rule_6_1_e" on a phone in a shop.
const Map<String, String> kRuleLabels = <String, String>{
  'rule_6_1_a': 'Rule 6(1)(a) - Name and address of the manufacturer or packer',
  'rule_6_1_c': 'Rule 6(1)(c) - Net quantity declaration',
  'rule_6_1_e': 'Rule 6(1)(e) - Retail sale price, inclusive of all taxes',
  'rule_6_1_g': 'Rule 6(1)(g) - Consumer care contact details',
  'schedule_ii': 'Rule 7(3) / Schedule II - Minimum height of the declaration',
};

String ruleLabel(String ruleId) => kRuleLabels[ruleId] ?? ruleId;

/// Scan Detail for a capture taken on this device.
///
/// Reads from the local row rather than the network, so an officer can still
/// see the last known verdict while out of coverage. [VerdictSyncService]
/// refreshes it whenever the server has something newer.
class ScanDetailScreen extends StatefulWidget {
  final String localId;
  final CaptureRecord? initialRecord;
  final DatabaseHelper? databaseHelper;
  final VerdictSyncService? verdictSyncService;

  const ScanDetailScreen({
    super.key,
    required this.localId,
    this.initialRecord,
    this.databaseHelper,
    this.verdictSyncService,
  });

  @override
  State<ScanDetailScreen> createState() => _ScanDetailScreenState();
}

class _ScanDetailScreenState extends State<ScanDetailScreen> {
  late final DatabaseHelper _db;
  late final VerdictSyncService _verdictSync;

  CaptureRecord? _record;
  bool _isLoading = true;
  bool _isRefreshing = false;

  @override
  void initState() {
    super.initState();
    _db = widget.databaseHelper ?? DatabaseHelper();
    _verdictSync = widget.verdictSyncService ?? VerdictSyncService();
    _record = widget.initialRecord;
    _isLoading = widget.initialRecord == null;
    _load();
  }

  Future<void> _load() async {
    try {
      final record = await _db.getCaptureById(widget.localId);
      if (!mounted) return;
      setState(() {
        _record = record ?? _record;
        _isLoading = false;
      });
    } catch (e) {
      debugPrint('[ScanDetail] Could not load capture: $e');
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _refresh() async {
    setState(() => _isRefreshing = true);
    await _verdictSync.refreshOnce();
    await _load();
    if (mounted) setState(() => _isRefreshing = false);
  }

  @override
  Widget build(BuildContext context) {
    final record = _record;

    return Scaffold(
      backgroundColor: AppColors.paper100,
      appBar: AppBar(
        backgroundColor: AppColors.ink900,
        foregroundColor: AppColors.paper000,
        title: Text(
          'Scan detail',
          style: AppTypography.base.copyWith(
            color: AppColors.paper000,
            fontWeight: FontWeight.w600,
          ),
        ),
        actions: [
          IconButton(
            tooltip: 'Check for an updated verdict',
            onPressed: _isRefreshing ? null : _refresh,
            icon: _isRefreshing
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.paper000),
                  )
                : const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : record == null
              ? _buildMissing()
              : RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
                    children: [
                      _buildVerdictCard(record),
                      const SizedBox(height: AppSpacing.space2),
                      if (record.ruleFailures.isNotEmpty) ...[
                        _buildRuleFailures(record),
                        const SizedBox(height: AppSpacing.space2),
                      ],
                      _buildEvidenceCard(record),
                    ],
                  ),
                ),
    );
  }

  Widget _buildMissing() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.space3),
        child: Text(
          'This capture is no longer on the device.',
          textAlign: TextAlign.center,
          style: AppTypography.base.copyWith(color: AppColors.ink600),
        ),
      ),
    );
  }

  Widget _buildVerdictCard(CaptureRecord record) {
    final verdict = record.verdict;
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              VerdictSealBadge(verdict: verdict, size: 48),
              const SizedBox(width: AppSpacing.space2),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      verdict.label,
                      style: AppTypography.lg.copyWith(
                        color: AppColors.ink900,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.space05),
                    StatusChip(status: record.toUiSyncStatus),
                  ],
                ),
              ),
            ],
          ),
          if (record.verdictSummary != null) ...[
            const SizedBox(height: AppSpacing.space2),
            Text(
              record.verdictSummary!,
              style: AppTypography.base.copyWith(color: AppColors.ink600),
            ),
          ],
          if (verdict == VerdictStatus.awaiting) ...[
            const SizedBox(height: AppSpacing.space2),
            Text(
              record.isSynced
                  ? 'The server has your evidence and is still assessing it. This screen updates automatically.'
                  : 'This capture has not been uploaded yet. It will be sent as soon as there is a connection.',
              style: AppTypography.xs.copyWith(color: AppColors.ink600),
            ),
          ],
          if (record.lastError != null && !record.isSynced) ...[
            const SizedBox(height: AppSpacing.space2),
            Container(
              padding: const EdgeInsets.all(AppSpacing.space1),
              decoration: BoxDecoration(
                color: AppColors.verdictPending.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(AppRadius.card),
              ),
              child: Text(
                record.lastError!,
                style: AppTypography.xs.copyWith(color: AppColors.ink900),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildRuleFailures(CaptureRecord record) {
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Declarations in breach',
            style: AppTypography.base.copyWith(
              color: AppColors.ink900,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: AppSpacing.space1),
          ...record.ruleFailures.map(
            (id) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.space1),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.close, size: 16, color: AppColors.verdictFail),
                  const SizedBox(width: AppSpacing.space1),
                  Expanded(
                    child: Text(
                      ruleLabel(id),
                      style: AppTypography.xs.copyWith(color: AppColors.ink900),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEvidenceCard(CaptureRecord record) {
    final capturedAt = DateTime.tryParse(record.capturedAtUtc)?.toLocal();
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Evidence record',
            style: AppTypography.base.copyWith(
              color: AppColors.ink900,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: AppSpacing.space1),
          if (record.productName != null && record.productName!.isNotEmpty)
            _row('Product', record.productName!),
          _row('Captured', capturedAt == null ? record.capturedAtUtc : _formatDateTime(capturedAt)),
          if (record.lat != null && record.lng != null)
            _row(
              'Location',
              '${record.lat!.toStringAsFixed(5)}, ${record.lng!.toStringAsFixed(5)}'
              '${record.accuracyMetres != null ? ' (+/-${record.accuracyMetres!.round()} m)' : ''}',
            ),
          _row('Reference', record.referenceObjectType.replaceAll('_', ' ')),
          _row('Package shape', record.productType),
          if (record.serverScanId != null) _row('Server scan', record.serverScanId!),
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.space1),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: AppTypography.xs.copyWith(color: AppColors.ink600),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.xs.copyWith(
                color: AppColors.ink900,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  static String _formatDateTime(DateTime dt) {
    String two(int v) => v.toString().padLeft(2, '0');
    return '${two(dt.day)}/${two(dt.month)}/${dt.year} ${two(dt.hour)}:${two(dt.minute)}';
  }

  Widget _card({required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.space2),
      decoration: BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.ink600.withValues(alpha: 0.15)),
      ),
      child: child,
    );
  }
}
