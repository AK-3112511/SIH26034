import 'package:flutter/material.dart';

import '../../../../core/theme/design_tokens.dart';

/// One tile in the Home screen's daily summary strip.
class MetricCard extends StatelessWidget {
  final String label;
  final int count;
  final Color color;
  final VoidCallback? onTap;

  const MetricCard({
    super.key,
    required this.label,
    required this.count,
    required this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.card),
      child: Container(
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
    ),
  );
}
}

/// Capture Item Card with Flat Pill Sync Status Chip (§5.4) & Origin Differentiation (§5.3)
