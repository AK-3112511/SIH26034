import 'package:flutter/material.dart';
import '../theme/design_tokens.dart';

/// Sync / Queue Status Enum
/// Per MetrologyAI_Design_System.md §5.4 & MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md §2
enum SyncStatus {
  synced,
  pendingUpload,
  failed,
}

/// Status Chip (Non-Verdict States)
/// Source: MetrologyAI_Design_System.md §5.4
///
/// Used for sync/queue status only (Synced, Pending Upload, Failed).
/// Deliberately a FLAT PILL SHAPE, distinct from the circular Seal Badge,
/// so field officers never confuse queue status with legal compliance verdicts.
class StatusChip extends StatelessWidget {
  final SyncStatus status;

  const StatusChip({
    super.key,
    required this.status,
  });

  Color get _color {
    switch (status) {
      case SyncStatus.synced:
        return AppColors.verdictPass;
      case SyncStatus.pendingUpload:
        return AppColors.verdictPending;
      case SyncStatus.failed:
        return AppColors.verdictFail;
    }
  }

  String get _label {
    switch (status) {
      case SyncStatus.synced:
        return 'Synced';
      case SyncStatus.pendingUpload:
        return 'Pending Upload';
      case SyncStatus.failed:
        return 'Failed';
    }
  }

  IconData get _icon {
    switch (status) {
      case SyncStatus.synced:
        return Icons.check_circle_outline;
      case SyncStatus.pendingUpload:
        return Icons.cloud_upload_outlined;
      case SyncStatus.failed:
        return Icons.error_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = _color;

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.space1,
        vertical: AppSpacing.space05,
      ),
      decoration: BoxDecoration(
        color: statusColor.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.sealBadge),
        border: Border.all(
          color: statusColor,
          width: 1.0,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(
            _icon,
            size: 14.0,
            color: statusColor,
          ),
          const SizedBox(width: AppSpacing.space05),
          Text(
            _label,
            style: AppTypography.xs.copyWith(
              color: statusColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
