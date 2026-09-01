import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/features/capture/services/card_detector.dart';

void main() {
  group('CardDetector (On-Device Shutter Gate)', () {
    late CardDetector detector;

    setUp(() {
      detector = CardDetector(throttleIntervalMs: 100);
    });

    test('validates ISO/IEC 7810 ID-1 standard aspect ratio range', () {
      expect(kIsoCardAspectRatio, closeTo(1.5858, 0.001));
      expect(kCardAspectRatioMin, 1.25);
      expect(kCardAspectRatioMax, 1.95);

      // Nominal ratio must fall safely inside tolerance band
      expect(kIsoCardAspectRatio >= kCardAspectRatioMin, isTrue);
      expect(kIsoCardAspectRatio <= kCardAspectRatioMax, isTrue);
    });

    test('enforces throttle interval between evaluated frames', () async {
      // First check should allow processing
      expect(detector.shouldProcessFrame(), isTrue);

      final dummyBytes = Uint8List(100);
      detector.fallbackDetect(yPlaneBytes: dummyBytes, width: 10, height: 10);

      // Immediate subsequent check should be throttled
      expect(detector.shouldProcessFrame(), isFalse);

      // Wait for throttle duration
      await Future.delayed(const Duration(milliseconds: 110));

      // After interval, should be allowed again
      expect(detector.shouldProcessFrame(), isTrue);
    });

    test('measures processing latency and produces telemetry result', () {
      final dummyBytes = Uint8List(200);
      final result = detector.fallbackDetect(
        yPlaneBytes: dummyBytes,
        width: 20,
        height: 10,
      );

      expect(result.processingTimeMs, greaterThanOrEqualTo(0));
      expect(result.isDetected, isFalse);
    });

    test('evaluates synthetic test card pattern', () {
      final cardBytes = Uint8List(200);
      cardBytes[0] = 0xAA;
      cardBytes[1] = 0xBB;

      final result = detector.fallbackDetect(
        yPlaneBytes: cardBytes,
        width: 20,
        height: 10,
      );

      expect(result.isDetected, isTrue);
      expect(result.confidence, greaterThan(0.9));
      expect(result.detectedAspectRatio, closeTo(1.5858, 0.01));
    });
  });
}
