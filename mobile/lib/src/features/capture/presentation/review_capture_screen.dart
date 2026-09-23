import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../../core/database/database_helper.dart';
import '../../../core/theme/design_tokens.dart';
import '../../scans/models/capture_record.dart';
import '../../scans/services/sync_worker.dart';
import 'capture_screen.dart';

/// Review Before Upload.
///
/// The last point at which a blurred shot, a card lying at an angle or the
/// wrong panel can be caught for free. Once a capture is queued it carries an
/// evidence hash, so a bad photo costs a second site visit. Nothing is written
/// to SQLite until the officer taps Confirm; tapping Retake deletes the file.
class ReviewCaptureScreen extends StatefulWidget {
  final String localId;
  final String imagePath;
  final DateTime capturedAtUtc;
  final double latitude;
  final double longitude;
  final double? accuracyMetres;
  final ProductType productType;
  final ReferenceCardType referenceCardType;
  final String deviceId;
  final DatabaseHelper? databaseHelper;
  final SyncWorker? syncWorker;

  const ReviewCaptureScreen({
    super.key,
    required this.localId,
    required this.imagePath,
    required this.capturedAtUtc,
    required this.latitude,
    required this.longitude,
    this.accuracyMetres,
    required this.productType,
    required this.referenceCardType,
    required this.deviceId,
    this.databaseHelper,
    this.syncWorker,
  });

  @override
  State<ReviewCaptureScreen> createState() => _ReviewCaptureScreenState();
}

class _ReviewCaptureScreenState extends State<ReviewCaptureScreen> {
  final TextEditingController _productNameController = TextEditingController();
  bool _isSaving = false;

  @override
  void dispose() {
    _productNameController.dispose();
    super.dispose();
  }

  Future<void> _retake() async {
    // The photo was never queued, so there is nothing to keep.
    try {
      final file = File(widget.imagePath);
      if (file.existsSync()) await file.delete();
    } catch (e) {
      debugPrint('[ReviewCapture] Could not delete discarded photo: $e');
    }
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _confirm() async {
    if (_isSaving) return;
    setState(() => _isSaving = true);

    final db = widget.databaseHelper ?? DatabaseHelper();
    final syncWorker = widget.syncWorker ?? SyncWorker();

    final productName = _productNameController.text.trim();
    final record = CaptureRecord(
      localId: widget.localId,
      imagePath: widget.imagePath,
      lat: widget.latitude,
      lng: widget.longitude,
      accuracyMetres: widget.accuracyMetres,
      capturedAtUtc: widget.capturedAtUtc.toIso8601String(),
      referenceObjectType: widget.referenceCardType.wireValue,
      productType: widget.productType.wireValue,
      productName: productName.isEmpty ? null : productName,
      deviceId: widget.deviceId,
      syncStatus: 'PENDING_UPLOAD',
      retryCount: 0,
    );

    try {
      await db.insertCapture(record);
    } catch (e) {
      debugPrint('[ReviewCapture] Could not queue capture: $e');
      if (!mounted) return;
      setState(() => _isSaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not save this capture to the queue: $e')),
      );
      return;
    }

    // Upload opportunistically now; WorkManager picks it up later if offline.
    unawaited(syncWorker.syncPendingCaptures());
    unawaited(syncWorker.scheduleOneOffSync());

    if (!mounted) return;
    Navigator.of(context).pop(<String, dynamic>{
      'localId': widget.localId,
      'path': widget.imagePath,
      'productType': widget.productType.wireValue,
      'referenceObjectType': widget.referenceCardType.wireValue,
      'productName': productName.isEmpty ? null : productName,
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.ink900,
      appBar: AppBar(
        backgroundColor: AppColors.ink900,
        foregroundColor: AppColors.paper000,
        elevation: 0,
        title: Text(
          'Review capture',
          style: AppTypography.base.copyWith(
            color: AppColors.paper000,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: Container(
                width: double.infinity,
                color: Colors.black,
                child: _buildPreview(),
              ),
            ),
            _buildDetails(),
          ],
        ),
      ),
    );
  }

  Widget _buildPreview() {
    final file = File(widget.imagePath);
    if (!file.existsSync()) {
      return Center(
        child: Text(
          'The photo could not be read back from storage.',
          style: AppTypography.xs.copyWith(color: AppColors.paper100),
        ),
      );
    }
    return InteractiveViewer(
      maxScale: 5.0,
      child: Center(
        child: Image.file(file, fit: BoxFit.contain),
      ),
    );
  }

  Widget _buildDetails() {
    return Container(
      padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
      decoration: const BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Check the declarations panel is sharp and the card is flat and fully visible.',
              style: AppTypography.xs.copyWith(color: AppColors.ink600),
            ),
            const SizedBox(height: AppSpacing.space2),
            Wrap(
              spacing: AppSpacing.space1,
              runSpacing: AppSpacing.space1,
              children: [
                _factChip(widget.referenceCardType.icon, widget.referenceCardType.label),
                _factChip(widget.productType.icon, widget.productType.label),
                _factChip(
                  Icons.place_outlined,
                  '${widget.latitude.toStringAsFixed(5)}, ${widget.longitude.toStringAsFixed(5)}'
                  '${widget.accuracyMetres != null ? ' (+/-${widget.accuracyMetres!.round()} m)' : ''}',
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.space2),
            TextField(
              controller: _productNameController,
              textCapitalization: TextCapitalization.words,
              maxLength: 200,
              decoration: InputDecoration(
                labelText: 'Brand / product name (optional)',
                helperText: 'Helps the repository group this with the same product.',
                counterText: '',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppRadius.card),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.space2),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _isSaving ? null : _retake,
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('Retake'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(0, 48),
                      foregroundColor: AppColors.ink900,
                      side: const BorderSide(color: AppColors.ink600),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.space2),
                Expanded(
                  flex: 2,
                  child: FilledButton.icon(
                    onPressed: _isSaving ? null : _confirm,
                    icon: _isSaving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: AppColors.paper000,
                            ),
                          )
                        : const Icon(Icons.check, size: 18),
                    label: Text(_isSaving ? 'Queueing...' : 'Confirm and queue'),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(0, 48),
                      backgroundColor: AppColors.ink900,
                      foregroundColor: AppColors.paper000,
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

  Widget _factChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.space1,
        vertical: AppSpacing.space05,
      ),
      decoration: BoxDecoration(
        color: AppColors.paper100,
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppColors.ink600),
          const SizedBox(width: AppSpacing.space05),
          Text(label, style: AppTypography.xs.copyWith(color: AppColors.ink900)),
        ],
      ),
    );
  }
}
