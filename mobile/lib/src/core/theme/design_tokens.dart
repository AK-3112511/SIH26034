import 'package:flutter/material.dart';

/// MetrologyAI Design Tokens
/// Source of Truth: MetrologyAI_Design_System.md

/// Section 2: Color System Tokens
class AppColors {
  AppColors._();

  /// Primary brand ink — navigation, headers, primary buttons
  static const Color ink900 = Color(0xFF12203B);

  /// Secondary text, inactive nav states
  static const Color ink600 = Color(0xFF3C4E70);

  /// App background — cool grey-green off-white
  static const Color paper100 = Color(0xFFF1F3F1);

  /// Card surfaces, elevated panels
  static const Color paper000 = Color(0xFFFFFFFF);

  /// Signature accent — seal badge ring, ruler ticks, signature CTA
  static const Color brass500 = Color(0xFFA6742C);

  /// PASS seal badge, success states
  static const Color verdictPass = Color(0xFF1E7A4D);

  /// FAIL seal badge, error states
  static const Color verdictFail = Color(0xFFB3261E);

  /// PENDING REVIEW seal badge, warning states
  static const Color verdictPending = Color(0xFFB5730B);

  /// CALIBRATION FAILED / neutral / unknown states
  static const Color verdictNeutral = Color(0xFF6B7280);
}

/// Section 3: Typography System Tokens
class AppTypography {
  AppTypography._();

  static const String fontDisplay = 'SpaceGrotesk';
  static const String fontBody = 'Inter';
  static const String fontMono = 'IBMPlexMono';

  /// Type scale (base 16px, 1.25 ratio): 12 / 16 / 20 / 25 / 31 / 39 / 49px
  static const TextStyle xs = TextStyle(
    fontFamily: fontBody,
    fontSize: 12.0,
    height: 1.33,
    letterSpacing: 0.2,
  );

  static const TextStyle base = TextStyle(
    fontFamily: fontBody,
    fontSize: 16.0,
    height: 1.5,
  );

  static const TextStyle lg = TextStyle(
    fontFamily: fontDisplay,
    fontSize: 20.0,
    height: 1.4,
    fontWeight: FontWeight.w500,
  );

  static const TextStyle xl = TextStyle(
    fontFamily: fontDisplay,
    fontSize: 25.0,
    height: 1.28,
    fontWeight: FontWeight.w600,
  );

  static const TextStyle display2xl = TextStyle(
    fontFamily: fontDisplay,
    fontSize: 31.0,
    height: 1.22,
    fontWeight: FontWeight.bold,
  );

  static const TextStyle display3xl = TextStyle(
    fontFamily: fontDisplay,
    fontSize: 39.0,
    height: 1.18,
    fontWeight: FontWeight.bold,
  );

  static const TextStyle display4xl = TextStyle(
    fontFamily: fontDisplay,
    fontSize: 49.0,
    height: 1.14,
    fontWeight: FontWeight.bold,
  );

  /// Data / Measurement Mono style
  static const TextStyle dataMono = TextStyle(
    fontFamily: fontMono,
    fontSize: 14.0,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.28, // +0.02em letter spacing for digit strings
  );
}

/// Section 4: Spacing & Layout Grid Tokens
class AppSpacing {
  AppSpacing._();

  static const double baseUnit = 8.0;

  static const double space05 = 4.0;
  static const double space1 = 8.0;
  static const double space2 = 16.0;
  static const double space3 = 24.0;
  static const double space4 = 32.0;
  static const double space5 = 40.0;
  static const double space6 = 48.0;
  static const double space8 = 64.0;
  static const double space10 = 80.0;
  static const double space12 = 96.0;
}

/// Section 4 & 5: Constraints & Radius Tokens
class AppConstraints {
  AppConstraints._();

  static const double minTouchTargetHeight = 48.0; // Gloved/field use requirement
  static const double mobileScreenMargin = 16.0;
  static const double calibrationTickHeight = 2.0;
  static const double calibrationTickInterval = 8.0;
}

class AppRadius {
  AppRadius._();

  static const double card = 4.0; // Small radius for official documentation feel
  static const double sealBadge = 9999.0; // Full pill/circle radius
}
