import 'package:flutter/material.dart';

import '../../../../core/theme/design_tokens.dart';
import '../../../../core/widgets/status_chip.dart';
import '../../../../core/widgets/verdict_seal_badge.dart';
import '../../models/capture_item.dart';
import '../../models/capture_record.dart';

/// One row in the Home screen list: a capture taken on this device, or a
/// follow-up task assigned from the dashboard.
class CaptureCard extends StatelessWidget {
  final CaptureItem capture;
  final VoidCallback? onTap;

  const CaptureCard({
    super.key,
    required this.capture,
    this.onTap,
  });

  String _formatTime(DateTime time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    return '$hour:$minute IST';
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.space1),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.card),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.space2),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Origin Badge & Status Chip Header (§5.3 Distinction)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  if (capture.isAssignedTask)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2.5),
                      decoration: BoxDecoration(
                        color: AppColors.ink900,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(
                            Icons.assignment_turned_in_outlined,
                            color: AppColors.brass500,
                            size: 12,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'ASSIGNED TASK',
                            style: AppTypography.dataMono.copyWith(
                              fontSize: 10,
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            ),
                          ),
                          if (capture.platform != null && capture.platform!.isNotEmpty) ...[
                            const SizedBox(width: 5),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                              decoration: BoxDecoration(
                                color: AppColors.brass500.withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(2),
                              ),
                              child: Text(
                                capture.platform!.toUpperCase(),
                                style: AppTypography.dataMono.copyWith(
                                  fontSize: 9,
                                  color: AppColors.brass500,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    )
                  else
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.paper100,
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: AppColors.ink600.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.camera_alt_outlined, color: AppColors.ink600, size: 11),
                          const SizedBox(width: 4),
                          Text(
                            'FIELD CAPTURE',
                            style: AppTypography.dataMono.copyWith(
                              fontSize: 9,
                              color: AppColors.ink600,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                  // Two separate signals: a flat pill for whether the photo
                  // uploaded, a circular seal for what the law says about it.
                  StatusChip(status: capture.syncStatus),
                  if (capture.verdict != VerdictStatus.awaiting) ...[
                    const SizedBox(width: AppSpacing.space1),
                    VerdictSealBadge(verdict: capture.verdict),
                  ],
                ],
              ),
              const SizedBox(height: AppSpacing.space1),

              // Product Title & Category
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

              const SizedBox(height: AppSpacing.space2),

              // ID & Timestamp Banner
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

              // Location Row
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

              // Statutory Follow-up Action Notice for Assigned Tasks
              if (capture.isAssignedTask && capture.followUpNote != null) ...[
                const SizedBox(height: AppSpacing.space1),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.space1,
                    vertical: AppSpacing.space05,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.verdictPending.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(AppRadius.card),
                    border: Border.all(color: AppColors.verdictPending.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline, color: AppColors.verdictPending, size: 13),
                      const SizedBox(width: 5),
                      Expanded(
                        child: Text(
                          capture.followUpNote!,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: AppTypography.xs.copyWith(
                            color: AppColors.ink900,
                            fontWeight: FontWeight.w500,
                            fontSize: 11,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
