import 'dart:async';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';
import '../../../core/config/app_config.dart';
import '../../../core/theme/design_tokens.dart';
import '../services/card_detector.dart';
import '../services/location_service.dart';
import 'review_capture_screen.dart';

/// The package geometry being inspected. Drives how the server dewarps the
/// principal display panel before measuring type height.
enum ProductType {
  box('Box', 'box', Icons.inventory_2_outlined),
  bottle('Bottle', 'bottle', Icons.local_drink_outlined),
  other('Other', 'other', Icons.category_outlined);

  final String label;

  /// Value sent as the `product_type` form field.
  final String wireValue;
  final IconData icon;
  const ProductType(this.label, this.wireValue, this.icon);
}

/// The calibration reference placed beside the package.
///
/// Both are ISO/IEC 7810 ID-1 (85.60 x 53.98 mm), which is what makes them
/// usable as a ruler; the distinction is recorded so the server knows which
/// object it is looking for. This is a different question from [ProductType],
/// and conflating the two is what previously sent "box" to the backend as the
/// thing it should measure against.
enum ReferenceCardType {
  debitCard('Debit / Credit card', 'debit_card', Icons.credit_card),
  panCard('PAN card', 'pan_card', Icons.badge_outlined);

  final String label;
  final String wireValue;
  final IconData icon;
  const ReferenceCardType(this.label, this.wireValue, this.icon);
}

/// Capture Screen with live camera and on-device card-detection shutter gate.
class CaptureScreen extends StatefulWidget {
  final CardDetector? cardDetector;
  final bool forceSimulator;
  final LocationService? locationService;

  const CaptureScreen({
    super.key,
    this.cardDetector,
    this.forceSimulator = false,
    this.locationService,
  });

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> with SingleTickerProviderStateMixin {
  CameraController? _cameraController;
  List<CameraDescription> _availableCameras = [];

  bool _isCameraInitialized = false;
  bool _isFlashOn = false;
  bool _isCardDetected = false;
  bool _isProcessingFrame = false;
  bool _isCapturing = false;

  int _lastLatencyMs = 0;
  double? _lastAspectRatio;
  String _statusMessage = 'Searching for reference card...';

  ProductType _selectedProductType = ProductType.box;
  ReferenceCardType _selectedCardType = ReferenceCardType.debitCard;

  late final CardDetector _detector;
  late final LocationService _locationService;

  LocationResult? _location;
  bool _isLocating = false;

  late AnimationController _guideAnimationController;
  late Animation<Color?> _guideColorAnimation;

  @override
  void initState() {
    super.initState();
    _detector = widget.cardDetector ?? CardDetector(throttleIntervalMs: 250);
    _locationService = widget.locationService ?? LocationService();

    _guideAnimationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 150),
    );

    _guideColorAnimation = ColorTween(
      begin: AppColors.verdictFail,
      end: AppColors.verdictPass,
    ).animate(
      CurvedAnimation(
        parent: _guideAnimationController,
        curve: Curves.easeInOut,
      ),
    );

    if (!widget.forceSimulator) {
      _initCamera();
    }
    unawaited(_acquireLocation());
  }

  @override
  void dispose() {
    _guideAnimationController.dispose();
    _cameraController?.stopImageStream().catchError((_) {});
    _cameraController?.dispose();
    super.dispose();
  }

  /// A capture without a GPS fix cannot be stamped into the Section 65B hash,
  /// so we ask for one as soon as the screen opens rather than at shutter time.
  Future<void> _acquireLocation() async {
    if (_isLocating) return;
    setState(() => _isLocating = true);
    final result = await _locationService.getCurrentLocation();
    if (!mounted) return;
    setState(() {
      _location = result;
      _isLocating = false;
    });
  }

  Future<void> _initCamera() async {
    try {
      _availableCameras = await availableCameras();
      if (_availableCameras.isNotEmpty) {
        final backCamera = _availableCameras.firstWhere(
          (c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => _availableCameras.first,
        );

        final controller = CameraController(
          backCamera,
          ResolutionPreset.high,
          enableAudio: false,
          imageFormatGroup: ImageFormatGroup.yuv420,
        );

        await controller.initialize();

        if (!mounted) return;

        setState(() {
          _cameraController = controller;
          _isCameraInitialized = true;
        });

        await controller.startImageStream(_handleCameraFrame);
      }
    } catch (e) {
      debugPrint('Camera initialization error / fallback: $e');
      if (mounted) {
        setState(() {
          _isCameraInitialized = false;
        });
      }
    }
  }

  void _handleCameraFrame(CameraImage image) {
    if (_isProcessingFrame || !_detector.shouldProcessFrame()) {
      return;
    }

    _isProcessingFrame = true;

    // Detection runs on OpenCV's native thread pool; the frame callback returns
    // immediately so the preview keeps its frame rate.
    unawaited(
      _detector
          .processGrayscalePlaneAsync(
        yPlaneBytes: image.planes[0].bytes,
        width: image.width,
        height: image.height,
      )
          .then((result) {
        if (mounted) _updateDetectionState(result);
      }).catchError((Object e) {
        debugPrint('Frame processing error: $e');
      }).whenComplete(() {
        _isProcessingFrame = false;
      }),
    );
  }

  void _updateDetectionState(CardDetectionResult result) {
    setState(() {
      _lastLatencyMs = result.processingTimeMs;
      _lastAspectRatio = result.detectedAspectRatio;
      _statusMessage = result.debugMessage ?? '';

      if (result.isDetected != _isCardDetected) {
        _isCardDetected = result.isDetected;
        if (_isCardDetected) {
          _guideAnimationController.forward();
        } else {
          _guideAnimationController.reverse();
        }
      }
    });
  }

  Future<void> _toggleFlash() async {
    if (_cameraController == null || !_isCameraInitialized) {
      setState(() {
        _isFlashOn = !_isFlashOn;
      });
      return;
    }

    try {
      final nextMode = _isFlashOn ? FlashMode.off : FlashMode.torch;
      await _cameraController!.setFlashMode(nextMode);
      setState(() {
        _isFlashOn = !_isFlashOn;
      });
    } catch (e) {
      debugPrint('Flash toggle error: $e');
    }
  }

  bool get _hasLocation => _location?.isSuccess ?? false;
  bool get _canCapture => _isCardDetected && _hasLocation && !_isCapturing;

  Future<void> _handleShutter() async {
    if (!_canCapture) return;

    setState(() {
      _isCapturing = true;
    });

    try {
      final localId = const Uuid().v4();
      final nowUtc = DateTime.now().toUtc();

      final docsDir = await getApplicationDocumentsDirectory();
      final capturesDir = Directory(p.join(docsDir.path, 'captures'));
      if (!await capturesDir.exists()) {
        await capturesDir.create(recursive: true);
      }
      final destinationPath = p.join(capturesDir.path, 'capture_$localId.jpg');

      if (_cameraController == null || !_isCameraInitialized) {
        // No camera means no evidence. Say so instead of writing a placeholder
        // that would later be uploaded as if it were a photograph.
        if (!mounted) return;
        setState(() => _isCapturing = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Camera is unavailable, so no photo can be recorded.'),
          ),
        );
        return;
      }

      final capturedFile = await _cameraController!.takePicture();
      await File(capturedFile.path).copy(destinationPath);

      if (!mounted) return;
      setState(() => _isCapturing = false);

      // Nothing is written to the queue until the officer confirms the shot.
      final saved = await Navigator.of(context).push<Map<String, dynamic>>(
        MaterialPageRoute(
          builder: (_) => ReviewCaptureScreen(
            localId: localId,
            imagePath: destinationPath,
            capturedAtUtc: nowUtc,
            latitude: _location!.latitude!,
            longitude: _location!.longitude!,
            accuracyMetres: _location!.accuracyMetres,
            productType: _selectedProductType,
            referenceCardType: _selectedCardType,
            deviceId: AppConfig().deviceId,
          ),
        ),
      );

      if (!mounted) return;
      if (saved != null) {
        Navigator.of(context).pop(saved);
      }
    } catch (e) {
      debugPrint('Capture error: $e');
      if (mounted) {
        setState(() {
          _isCapturing = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not take the photo: $e')),
        );
      }
    }
  }

  /// Debug-only helper for exercising the shutter gate on a desktop host.
  /// Never compiled into a release build.
  void _simulateCardToggle() {
    final newDetection = !_isCardDetected;
    _updateDetectionState(
      CardDetectionResult(
        isDetected: newDetection,
        detectedAspectRatio: newDetection ? kIsoCardAspectRatio : null,
        confidence: newDetection ? 0.96 : 0.0,
        processingTimeMs: 14,
        debugMessage: newDetection ? 'Simulated card detected' : 'Simulated card removed',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.ink900,
      body: SafeArea(
        child: Stack(
          children: [
            Positioned.fill(child: _buildCameraPreview()),
            Positioned(
              top: AppSpacing.space2,
              left: AppConstraints.mobileScreenMargin,
              right: AppConstraints.mobileScreenMargin,
              child: _buildTopControls(),
            ),
            Positioned.fill(child: _buildGuideOverlay()),
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: _buildBottomControls(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCameraPreview() {
    if (_isCameraInitialized && _cameraController != null) {
      // Show the sensor frame at its true aspect ratio. Stretching it would
      // misrepresent the geometry the officer is lining the card up against.
      return Center(
        child: AspectRatio(
          aspectRatio: 1 / _cameraController!.value.aspectRatio,
          child: CameraPreview(_cameraController!),
        ),
      );
    }

    return Container(
      color: AppColors.ink900,
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.camera_alt_outlined,
              size: 48.0,
              color: AppColors.paper100.withValues(alpha: 0.4),
            ),
            const SizedBox(height: AppSpacing.space2),
            Text(
              'Camera unavailable',
              style: AppTypography.xs.copyWith(
                color: AppColors.paper100.withValues(alpha: 0.6),
                letterSpacing: 1.2,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (kDebugMode) ...[
              const SizedBox(height: AppSpacing.space1),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.brass500,
                  side: const BorderSide(color: AppColors.brass500),
                  minimumSize: const Size(180, 48),
                ),
                onPressed: _simulateCardToggle,
                icon: Icon(
                  _isCardDetected ? Icons.check_circle : Icons.credit_card,
                  size: 16.0,
                ),
                label: Text(
                  _isCardDetected ? 'Card in frame (tap to remove)' : 'Simulate reference card',
                  style: AppTypography.xs.copyWith(
                    fontWeight: FontWeight.w600,
                    color: AppColors.brass500,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildTopControls() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        IconButton(
          tooltip: 'Back',
          icon: const Icon(Icons.arrow_back, color: AppColors.paper000),
          onPressed: () => Navigator.of(context).pop(),
        ),
        Tooltip(
          message: _statusMessage,
          child: Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.space1,
              vertical: AppSpacing.space05,
            ),
            decoration: BoxDecoration(
              color: AppColors.ink900.withValues(alpha: 0.7),
              borderRadius: BorderRadius.circular(AppRadius.card),
              border: Border.all(
                color: AppColors.brass500.withValues(alpha: 0.5),
                width: 1.0,
              ),
            ),
            child: Text(
              '${_lastLatencyMs}ms | ${_isCardDetected ? "CARD DETECTED" : "NO CARD"}',
              style: AppTypography.dataMono.copyWith(
                fontSize: 11.0,
                color: _isCardDetected ? AppColors.verdictPass : AppColors.paper000,
              ),
            ),
          ),
        ),
        IconButton(
          tooltip: 'Toggle flash',
          icon: Icon(
            _isFlashOn ? Icons.flash_on : Icons.flash_off,
            color: _isFlashOn ? AppColors.brass500 : AppColors.paper000,
          ),
          onPressed: _toggleFlash,
        ),
      ],
    );
  }

  Widget _buildGuideOverlay() {
    return AnimatedBuilder(
      animation: _guideAnimationController,
      builder: (context, child) {
        final boxColor = _guideColorAnimation.value ?? AppColors.verdictFail;

        return IgnorePointer(
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 220.0,
                  height: 138.0, // 220 / 1.586 ~= 138.7 (ISO/IEC 7810 ID-1)
                  decoration: BoxDecoration(
                    color: boxColor.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(AppRadius.card),
                    border: Border.all(color: boxColor, width: 2.5),
                  ),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _isCardDetected ? Icons.check_circle_outline : Icons.crop_free,
                          color: boxColor,
                          size: 32.0,
                        ),
                        const SizedBox(height: AppSpacing.space05),
                        Text(
                          _isCardDetected ? 'CARD DETECTED' : 'PLACE CARD HERE',
                          style: AppTypography.xs.copyWith(
                            color: boxColor,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 0.8,
                          ),
                        ),
                        if (_lastAspectRatio != null && _isCardDetected)
                          Text(
                            'Ratio: ${_lastAspectRatio!.toStringAsFixed(2)}',
                            style: AppTypography.dataMono.copyWith(
                              fontSize: 10.0,
                              color: boxColor,
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildBottomControls() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppConstraints.mobileScreenMargin,
        vertical: AppSpacing.space2,
      ),
      decoration: BoxDecoration(
        color: AppColors.ink900.withValues(alpha: 0.92),
        border: Border(
          top: BorderSide(
            color: AppColors.ink600.withValues(alpha: 0.3),
            width: 1.0,
          ),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!_hasLocation) _buildLocationBanner(),
          _buildReferenceCardSelector(),
          const SizedBox(height: AppSpacing.space1),
          _buildProductTypeSelector(),
          const SizedBox(height: AppSpacing.space3),
          _buildShutterButton(),
          const SizedBox(height: AppSpacing.space2),
          Text(
            _shutterHint,
            textAlign: TextAlign.center,
            style: AppTypography.xs.copyWith(
              color: AppColors.paper100,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  String get _shutterHint {
    if (!_hasLocation) return 'Location is required before you can capture evidence.';
    if (!_isCardDetected) return 'Place a debit or PAN card flat beside the product.';
    return 'Frame the declarations panel and the card together, then capture.';
  }

  Widget _buildLocationBanner() {
    final result = _location;
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.space2),
      padding: const EdgeInsets.all(AppSpacing.space2),
      decoration: BoxDecoration(
        color: AppColors.verdictPending.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.verdictPending.withValues(alpha: 0.6)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.location_off_outlined, color: AppColors.verdictPending, size: 20),
          const SizedBox(width: AppSpacing.space1),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _isLocating
                      ? 'Getting a GPS fix...'
                      : (result?.message ??
                          'MetrologyAI needs your location to stamp this capture.'),
                  style: AppTypography.xs.copyWith(color: AppColors.paper000),
                ),
                if (!_isLocating && result != null) ...[
                  const SizedBox(height: AppSpacing.space05),
                  Row(
                    children: [
                      if (result.isRetryable)
                        TextButton(
                          onPressed: _acquireLocation,
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.brass500,
                            minimumSize: const Size(0, 36),
                          ),
                          child: const Text('Try again'),
                        ),
                      if (result.failure == LocationFailure.permissionDeniedForever)
                        TextButton(
                          onPressed: () => _locationService.openPermissionSettings(),
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.brass500,
                            minimumSize: const Size(0, 36),
                          ),
                          child: const Text('Open settings'),
                        ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReferenceCardSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'REFERENCE CARD',
          style: AppTypography.xs.copyWith(
            color: AppColors.paper100.withValues(alpha: 0.7),
            letterSpacing: 1.0,
            fontSize: 10,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: AppSpacing.space05),
        Row(
          children: ReferenceCardType.values.map((type) {
            final isSelected = _selectedCardType == type;
            return Padding(
              padding: const EdgeInsets.only(right: AppSpacing.space1),
              child: ChoiceChip(
                label: Text(
                  type.label,
                  style: AppTypography.xs.copyWith(
                    color: isSelected ? AppColors.paper000 : AppColors.paper100,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
                avatar: Icon(
                  type.icon,
                  size: 16,
                  color: isSelected ? AppColors.paper000 : AppColors.paper100,
                ),
                selected: isSelected,
                selectedColor: AppColors.ink600,
                backgroundColor: AppColors.paper000.withValues(alpha: 0.1),
                side: BorderSide(
                  color: isSelected ? AppColors.brass500 : AppColors.ink600.withValues(alpha: 0.4),
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppRadius.card),
                ),
                onSelected: (selected) {
                  if (selected) setState(() => _selectedCardType = type);
                },
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildProductTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'PACKAGE SHAPE',
          style: AppTypography.xs.copyWith(
            color: AppColors.paper100.withValues(alpha: 0.7),
            letterSpacing: 1.0,
            fontSize: 10,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: AppSpacing.space05),
        Row(
          children: ProductType.values.map((type) {
            final isSelected = _selectedProductType == type;
            return Padding(
              padding: const EdgeInsets.only(right: AppSpacing.space1),
              child: ChoiceChip(
                label: Text(
                  type.label,
                  style: AppTypography.xs.copyWith(
                    color: isSelected ? AppColors.paper000 : AppColors.paper100,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
                avatar: Icon(
                  type.icon,
                  size: 16,
                  color: isSelected ? AppColors.paper000 : AppColors.paper100,
                ),
                selected: isSelected,
                selectedColor: AppColors.ink600,
                backgroundColor: AppColors.paper000.withValues(alpha: 0.1),
                side: BorderSide(
                  color: isSelected ? AppColors.brass500 : AppColors.ink600.withValues(alpha: 0.4),
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppRadius.card),
                ),
                onSelected: (selected) {
                  if (selected) setState(() => _selectedProductType = type);
                },
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildShutterButton() {
    return Semantics(
      button: true,
      enabled: _canCapture,
      label: 'Capture evidence photo',
      child: GestureDetector(
        onTap: _canCapture ? _handleShutter : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          width: 72.0,
          height: 72.0,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(
              color: _canCapture ? AppColors.brass500 : AppColors.ink600.withValues(alpha: 0.4),
              width: 3.0,
            ),
          ),
          child: Center(
            child: Container(
              width: 56.0,
              height: 56.0,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color:
                    _canCapture ? AppColors.brass500 : AppColors.ink600.withValues(alpha: 0.3),
              ),
              child: _isCapturing
                  ? const Center(
                      child: SizedBox(
                        width: 24.0,
                        height: 24.0,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: AppColors.paper000,
                        ),
                      ),
                    )
                  : Icon(
                      _canCapture ? Icons.camera_alt : Icons.lock_outline,
                      color: _canCapture ? AppColors.paper000 : AppColors.ink600,
                      size: 28.0,
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
