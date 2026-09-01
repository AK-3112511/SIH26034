import 'package:flutter/material.dart';
import 'design_tokens.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: AppColors.paper100,
      colorScheme: const ColorScheme.light(
        primary: AppColors.ink900,
        secondary: AppColors.brass500,
        surface: AppColors.paper000,
        error: AppColors.verdictFail,
        onPrimary: AppColors.paper000,
        onSecondary: AppColors.paper000,
        onSurface: AppColors.ink900,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.ink900,
        foregroundColor: AppColors.paper000,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontFamily: AppTypography.fontDisplay,
          fontSize: 18.0,
          fontWeight: FontWeight.w600,
          color: AppColors.paper000,
        ),
      ),
      cardTheme: CardThemeData(
        color: AppColors.paper000,
        elevation: 0,
        shape: RoundedRectangleBorder(
          side: const BorderSide(color: AppColors.ink600, width: 0.5),
          borderRadius: BorderRadius.circular(AppRadius.card),
        ),
        margin: const EdgeInsets.symmetric(
          horizontal: AppConstraints.mobileScreenMargin,
          vertical: AppSpacing.space1,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.ink900,
          foregroundColor: AppColors.paper000,
          minimumSize: const Size.fromHeight(AppConstraints.minTouchTargetHeight),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.card),
          ),
          textStyle: const TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: 16.0,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.ink900,
          backgroundColor: AppColors.paper000,
          minimumSize: const Size.fromHeight(AppConstraints.minTouchTargetHeight),
          side: const BorderSide(color: AppColors.ink900, width: 1.0),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.card),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.paper000,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.space2,
          vertical: AppSpacing.space2,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
          borderSide: const BorderSide(color: AppColors.ink600, width: 1.0),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
          borderSide: BorderSide(
            color: AppColors.ink600.withValues(alpha: 0.5),
            width: 1.0,
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
          borderSide: const BorderSide(color: AppColors.brass500, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
          borderSide: const BorderSide(color: AppColors.verdictFail, width: 1.0),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
          borderSide: const BorderSide(color: AppColors.verdictFail, width: 1.5),
        ),
        labelStyle: AppTypography.xs.copyWith(color: AppColors.ink600),
        hintStyle: AppTypography.base.copyWith(
          color: AppColors.ink600.withValues(alpha: 0.5),
        ),
        errorStyle: AppTypography.xs.copyWith(color: AppColors.verdictFail),
      ),
      textTheme: const TextTheme(
        displayLarge: AppTypography.display4xl,
        displayMedium: AppTypography.display3xl,
        displaySmall: AppTypography.display2xl,
        headlineMedium: AppTypography.xl,
        titleMedium: AppTypography.lg,
        bodyLarge: AppTypography.base,
        bodySmall: AppTypography.xs,
      ),
    );
  }
}
