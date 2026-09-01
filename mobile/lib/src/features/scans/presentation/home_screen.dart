import 'package:flutter/material.dart';
import '../../../core/theme/design_tokens.dart';
import '../../../core/widgets/calibration_tick_rule.dart';
import '../../../core/widgets/status_chip.dart';
import '../../auth/data/auth_service.dart';
import '../../auth/presentation/login_screen.dart';
import '../models/capture_item.dart';

/// Home / Today's Scans Screen (Mobile UX §2, Screen 2)
///
/// Landing screen after LMO login.
/// Lists today's captures with sync status chips (Synced / Pending Upload / Failed).
/// Features big bottom-anchored "New Scan" primary button.
class HomeScreen extends StatefulWidget {
  final List<CaptureItem>? initialCaptures;

  const HomeScreen({
    super.key,
    this.initialCaptures,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late List<CaptureItem> _captures;
  bool _showingMockData = false;

  @override
  void initState() {
    super.initState();
    // Default is empty as specified: "Home screen data can be mocked/empty for now since no captures exist yet"
    _captures = widget.initialCaptures ?? [];
  }

  void _toggleDataMode() {
    setState(() {
      _showingMockData = !_showingMockData;
      if (_showingMockData) {
        _captures = CaptureItem.mockItems();
      } else {
        _captures = [];
      }
    });
  }

  void _handleLogout() {
    AuthService().logout();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => const LoginScreen(),
      ),
    );
  }

  void _handleNewScan() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: AppColors.ink900,
        content: Row(
          children: [
            const Icon(Icons.camera_alt_outlined, color: AppColors.brass500, size: 20),
            const SizedBox(width: AppSpacing.space1),
            Expanded(
              child: Text(
                'Phase 2.2: AR Guide Capture & Reference Card Detection queued.',
                style: AppTypography.xs.copyWith(color: AppColors.paper000),
              ),
            ),
          ],
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = AuthService().currentUser;
    final officerName = user?.fullName.isNotEmpty == true ? user!.fullName : 'Field Officer';
    final district = user?.district?.isNotEmpty == true ? user!.district! : 'Jurisdiction';

    final syncedCount = _captures.where((c) => c.syncStatus == SyncStatus.synced).length;
    final pendingCount = _captures.where((c) => c.syncStatus == SyncStatus.pendingUpload).length;
    final failedCount = _captures.where((c) => c.syncStatus == SyncStatus.failed).length;

    return Scaffold(
      backgroundColor: AppColors.paper100,
      appBar: AppBar(
        title: const Text('MetrologyAI — Field LMO'),
        actions: [
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout, color: AppColors.paper000),
            onPressed: _handleLogout,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Scrollable Content
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
                children: [
                  // Officer Identity & Status Card
                  Card(
                    margin: EdgeInsets.zero,
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.space2),
                      child: Row(
                        children: [
                          Container(
                            width: 40.0,
                            height: 40.0,
                            decoration: BoxDecoration(
                              color: AppColors.ink900,
                              borderRadius: BorderRadius.circular(AppRadius.card),
                            ),
                            child: const Icon(
                              Icons.verified_user,
                              color: AppColors.brass500,
                              size: 22.0,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.space2),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  officerName,
                                  style: AppTypography.base.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: AppColors.ink900,
                                  ),
                                ),
                                const SizedBox(height: AppSpacing.space05),
                                Text(
                                  'District: $district • PCR 2011 Active',
                                  style: AppTypography.xs.copyWith(
                                    color: AppColors.ink600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          // Toggle button to preview mock data vs empty state
                          OutlinedButton(
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size(80, 36),
                              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.space1),
                            ),
                            onPressed: _toggleDataMode,
                            child: Text(
                              _showingMockData ? 'Empty' : 'Preview',
                              style: AppTypography.xs.copyWith(
                                color: AppColors.ink900,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // Signature Calibration Tick Rule divider
                  const CalibrationTickRule(),

                  // Today's Scans Header & Metric Summary
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            "Today's Scans",
                            style: AppTypography.lg,
                          ),
                          const SizedBox(height: AppSpacing.space05),
                          Text(
                            'Field capture log & synchronisation state',
                            style: AppTypography.xs.copyWith(color: AppColors.ink600),
                          ),
                        ],
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.space1,
                          vertical: AppSpacing.space05,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.paper000,
                          borderRadius: BorderRadius.circular(AppRadius.card),
                          border: Border.all(
                            color: AppColors.ink600.withValues(alpha: 0.3),
                            width: 1.0,
                          ),
                        ),
                        child: Text(
                          'TOTAL: ${_captures.length}',
                          style: AppTypography.dataMono.copyWith(
                            fontSize: 12.0,
                            fontWeight: FontWeight.bold,
                            color: AppColors.ink900,
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: AppSpacing.space2),

                  // Metrics Chips
                  Row(
                    children: [
                      Expanded(
                        child: _MetricCard(
                          label: 'Synced',
                          count: syncedCount,
                          color: AppColors.verdictPass,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.space1),
                      Expanded(
                        child: _MetricCard(
                          label: 'Pending',
                          count: pendingCount,
                          color: AppColors.verdictPending,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.space1),
                      Expanded(
                        child: _MetricCard(
                          label: 'Failed',
                          count: failedCount,
                          color: AppColors.verdictFail,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: AppSpacing.space3),

                  // Captures List or Empty State
                  if (_captures.isEmpty) ...[
                    _buildEmptyState(),
                  ] else ...[
                    ..._captures.map((capture) => _CaptureCard(capture: capture)),
                  ],

                  const SizedBox(height: AppSpacing.space2),
                ],
              ),
            ),

            // Bottom Anchored Primary Action Container
            // Per §8: 48px minimum touch target, bottom-anchored within thumb reach
            Container(
              padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
              decoration: BoxDecoration(
                color: AppColors.paper000,
                border: Border(
                  top: BorderSide(
                    color: AppColors.ink600.withValues(alpha: 0.2),
                    width: 1.0,
                  ),
                ),
              ),
              child: ElevatedButton.icon(
                onPressed: _handleNewScan,
                icon: const Icon(Icons.camera_alt, color: AppColors.paper000),
                label: const Text('NEW SCAN (AR GUIDE)'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.space4),
      decoration: BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(
          color: AppColors.ink600.withValues(alpha: 0.2),
          width: 1.0,
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 56.0,
            height: 56.0,
            decoration: BoxDecoration(
              color: AppColors.paper100,
              borderRadius: BorderRadius.circular(AppRadius.card),
            ),
            child: const Icon(
              Icons.document_scanner_outlined,
              color: AppColors.ink600,
              size: 30.0,
            ),
          ),
          const SizedBox(height: AppSpacing.space2),
          const Text(
            'No Captures Recorded Today',
            style: AppTypography.lg,
          ),
          const SizedBox(height: AppSpacing.space1),
          Text(
            'Evidence capture log is empty. Use the button below to initiate compliance capture with reference card calibration.',
            textAlign: TextAlign.center,
            style: AppTypography.xs.copyWith(color: AppColors.ink600),
          ),
          const SizedBox(height: AppSpacing.space2),
          Text(
            '(Tap "Preview" above to test populated captures with sync status chips)',
            style: AppTypography.dataMono.copyWith(
              fontSize: 12.0,
              color: AppColors.brass500,
            ),
          ),
        ],
      ),
    );
  }
}

/// Metric Counter Card
class _MetricCard extends StatelessWidget {
  final String label;
  final int count;
  final Color color;

  const _MetricCard({
    required this.label,
    required this.count,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.space1,
        vertical: AppSpacing.space1,
      ),
      decoration: BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(
          color: color.withValues(alpha: 0.4),
          width: 1.0,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label.toUpperCase(),
            style: AppTypography.xs.copyWith(
              color: AppColors.ink600,
              fontWeight: FontWeight.w600,
              fontSize: 11.0,
            ),
          ),
          const SizedBox(height: AppSpacing.space05),
          Text(
            '$count',
            style: AppTypography.dataMono.copyWith(
              fontSize: 18.0,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

/// Capture Item Card with Flat Pill Sync Status Chip (§5.4)
class _CaptureCard extends StatelessWidget {
  final CaptureItem capture;

  const _CaptureCard({required this.capture});

  String _formatTime(DateTime time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    return '$hour:$minute IST';
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.space1),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.space2),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        capture.productName,
                        style: AppTypography.base.copyWith(
                          fontWeight: FontWeight.w600,
                          color: AppColors.ink900,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.space05),
                      Text(
                        capture.category,
                        style: AppTypography.xs.copyWith(
                          color: AppColors.ink600,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.space1),
                // Flat Pill Sync Status Chip per §5.4 (distinct from circular Seal Badge)
                StatusChip(status: capture.syncStatus),
              ],
            ),
            const SizedBox(height: AppSpacing.space2),
            Container(
              padding: const EdgeInsets.all(AppSpacing.space1),
              decoration: BoxDecoration(
                color: AppColors.paper100,
                borderRadius: BorderRadius.circular(AppRadius.card),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    capture.id,
                    style: AppTypography.dataMono.copyWith(
                      fontSize: 12.0,
                      color: AppColors.ink900,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    _formatTime(capture.timestamp),
                    style: AppTypography.dataMono.copyWith(
                      fontSize: 12.0,
                      color: AppColors.ink600,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.space1),
            Row(
              children: [
                const Icon(
                  Icons.location_on_outlined,
                  color: AppColors.ink600,
                  size: 14.0,
                ),
                const SizedBox(width: AppSpacing.space05),
                Expanded(
                  child: Text(
                    capture.location,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.xs.copyWith(
                      color: AppColors.ink600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
