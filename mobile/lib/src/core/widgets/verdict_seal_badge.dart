import 'package:flutter/material.dart';

import '../../features/scans/models/capture_record.dart';
import '../theme/design_tokens.dart';

/// Circular seal for a legal compliance verdict.
///
/// Deliberately a different *shape* from [StatusChip], which is a flat pill:
/// an officer glancing at a list must never read "upload failed" as
/// "non-compliant". Colour alone would not carry that distinction for a
/// colour-blind user, so shape and icon do the work and colour reinforces it.
class VerdictSealBadge extends StatelessWidget {
  final VerdictStatus verdict;

  /// 24 for list rows, larger on a detail screen.
  final double size;
  final bool showLabel;

  const VerdictSealBadge({
    super.key,
    required this.verdict,
    this.size = 24.0,
    this.showLabel = false,
  });

  Color get _color {
    switch (verdict) {
      case VerdictStatus.passed:
        return AppColors.verdictPass;
      case VerdictStatus.failed:
        return AppColors.verdictFail;
      case VerdictStatus.pendingReview:
        return AppColors.verdictPending;
      case VerdictStatus.calibrationFailed:
      case VerdictStatus.processingFailed:
        return AppColors.ink600;
      case VerdictStatus.awaiting:
        return AppColors.verdictNeutral;
    }
  }

  IconData get _icon {
    switch (verdict) {
      case VerdictStatus.passed:
        return Icons.verified_outlined;
      case VerdictStatus.failed:
        return Icons.gavel_outlined;
      case VerdictStatus.pendingReview:
        return Icons.hourglass_top_outlined;
      case VerdictStatus.calibrationFailed:
        return Icons.straighten_outlined;
      case VerdictStatus.processingFailed:
        return Icons.report_gmailerrorred_outlined;
      case VerdictStatus.awaiting:
        return Icons.more_horiz;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _color;
    final seal = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color.withValues(alpha: 0.12),
        border: Border.all(color: color, width: 1.5),
      ),
      child: Icon(_icon, size: size * 0.6, color: color),
    );

    if (!showLabel) {
      return Semantics(label: 'Verdict: ${verdict.label}', child: seal);
    }

    return Semantics(
      label: 'Verdict: ${verdict.label}',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          seal,
          const SizedBox(width: AppSpacing.space1),
          Text(
            verdict.label,
            style: AppTypography.xs.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
