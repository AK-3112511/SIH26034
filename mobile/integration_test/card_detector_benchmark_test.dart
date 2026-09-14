// ignore_for_file: avoid_print
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mobile/src/features/capture/services/card_detector.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Native OpenCV Real-Device Performance Benchmark (ARM64)', () {
    late CardDetector detector;

    setUp(() {
      detector = CardDetector(throttleIntervalMs: 0); // Disable throttle for raw benchmark
    });

    Uint8List generateTestFrame({
      required int width,
      required int height,
      bool includeCard = true,
    }) {
      final buffer = Uint8List(width * height);
      // Fill background with textured noise/gradient
      for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
          buffer[y * width + x] = ((x * 128 / width) + (y * 127 / height) + ((x ^ y) & 0x1F)).toInt() % 256;
        }
      }

      if (includeCard) {
        // Draw a simulated reference card with ISO/IEC 7810 aspect ratio ~1.5858
        // e.g., 200 width, 126 height (200 / 126 = 1.587)
        final cardW = (width * 0.35).round();
        final cardH = (cardW / 1.5858).round();
        final startX = (width - cardW) ~/ 2;
        final startY = (height - cardH) ~/ 2;

        for (int y = startY; y < startY + cardH; y++) {
          for (int x = startX; x < startX + cardW; x++) {
            // Draw card interior with distinct high contrast luminance
            if (x == startX || x == startX + cardW - 1 || y == startY || y == startY + cardH - 1) {
              buffer[y * width + x] = 255; // sharp white border
            } else {
              buffer[y * width + x] = 220; // light gray interior
            }
          }
        }
      }

      return buffer;
    }

    testWidgets('Native CV execution is <=35ms/frame with 30+ FPS maintained on device',
        (WidgetTester tester) async {
      print('\n============================================================');
      print('=== METROLOGY AI REAL-DEVICE OPENCV PERFORMANCE BENCHMARK ===');
      print('============================================================\n');

      const width = 640;
      const height = 480;
      final testFrame = generateTestFrame(width: width, height: height, includeCard: true);

      // Warm-up run (JIT/FFI library initialization)
      for (int i = 0; i < 5; i++) {
        detector.processGrayscalePlane(
          yPlaneBytes: testFrame,
          width: width,
          height: height,
        );
      }

      // Benchmark iterations
      const iterations = 50;
      final latencies = <int>[];
      int detectedCount = 0;

      final overallStopwatch = Stopwatch()..start();

      for (int i = 0; i < iterations; i++) {
        final result = detector.processGrayscalePlane(
          yPlaneBytes: testFrame,
          width: width,
          height: height,
        );

        latencies.add(result.processingTimeMs);
        if (result.isDetected) {
          detectedCount++;
        }
      }

      overallStopwatch.stop();

      latencies.sort();
      final minMs = latencies.first;
      final maxMs = latencies.last;
      final avgMs = latencies.reduce((a, b) => a + b) / latencies.length;
      final medianMs = latencies[latencies.length ~/ 2];
      final p95Ms = latencies[(latencies.length * 0.95).floor()];
      final theoreticalFps = (1000.0 / (avgMs > 0 ? avgMs : 1)).clamp(0, 1000);

      print('Benchmark Results:');
      print('  - Resolution: ${width}x$height (Y-plane luminance)');
      print('  - Sample Count: $iterations frames');
      print('  - Min Latency: ${minMs}ms');
      print('  - Max Latency: ${maxMs}ms');
      print('  - Mean Latency: ${avgMs.toStringAsFixed(2)}ms');
      print('  - Median Latency: ${medianMs}ms');
      print('  - 95th Percentile: ${p95Ms}ms');
      print('  - Card Detection Success Rate: ${(detectedCount / iterations * 100).toStringAsFixed(1)}%');
      print('  - Raw Native CV Throughput: ${theoreticalFps.toStringAsFixed(1)} FPS');
      print('  - Throttled Duty Cycle (250ms): ${(avgMs / 250.0 * 100).toStringAsFixed(2)}% CPU time');
      print('\nVerdict:');
      if (avgMs <= 35.0) {
        print('  >>> [PASS] Native CV execution is <= 35ms/frame target (Actual: ${avgMs.toStringAsFixed(2)}ms)');
      } else {
        print('  >>> [FAIL] Native CV execution exceeded 35ms/frame (Actual: ${avgMs.toStringAsFixed(2)}ms)');
      }
      print('============================================================\n');

      expect(avgMs, lessThanOrEqualTo(35.0),
          reason: 'Native OpenCV pipeline must execute in <= 35ms on mobile hardware to avoid camera stutter');
      expect(avgMs, greaterThanOrEqualTo(0));
    });
  });
}
