import 'package:flutter/material.dart';
import '../theme/design_tokens.dart';

/// Signature Element: Calibration Tick Rule
/// Source: MetrologyAI_Design_System.md §1 & §4
///
/// A structural divider featuring millimeter-style tick marks every 8px
/// (matching AppSpacing.baseUnit), with a baseline height of 2px in brass-500.
class CalibrationTickRule extends StatelessWidget {
  final double height;
  final Color color;
  final double tickInterval;
  final EdgeInsetsGeometry margin;

  const CalibrationTickRule({
    super.key,
    this.height = 6.0,
    this.color = AppColors.brass500,
    this.tickInterval = AppConstraints.calibrationTickInterval,
    this.margin = const EdgeInsets.symmetric(vertical: AppSpacing.space2),
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      height: height,
      width: double.infinity,
      child: CustomPaint(
        painter: _CalibrationRulerPainter(
          color: color,
          tickInterval: tickInterval,
          baselineHeight: AppConstraints.calibrationTickHeight,
        ),
      ),
    );
  }
}

class _CalibrationRulerPainter extends CustomPainter {
  final Color color;
  final double tickInterval;
  final double baselineHeight;

  _CalibrationRulerPainter({
    required this.color,
    required this.tickInterval,
    required this.baselineHeight,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.0
      ..style = PaintingStyle.fill;

    // Draw baseline ruler (2px fixed height)
    final baselineY = size.height - baselineHeight;
    canvas.drawRect(
      Rect.fromLTWH(0, baselineY, size.width, baselineHeight),
      paint,
    );

    // Draw calibration tick marks every 8px
    int tickCount = (size.width / tickInterval).floor();
    for (int i = 0; i <= tickCount; i++) {
      final x = i * tickInterval;
      // Alternate between major (full height) and minor (half height) ticks
      final tickTop = (i % 5 == 0) ? 0.0 : size.height * 0.4;
      canvas.drawLine(
        Offset(x, tickTop),
        Offset(x, baselineY),
        paint..strokeWidth = 1.0,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _CalibrationRulerPainter oldDelegate) {
    return oldDelegate.color != color ||
        oldDelegate.tickInterval != tickInterval ||
        oldDelegate.baselineHeight != baselineHeight;
  }
}
