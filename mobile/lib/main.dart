import 'package:flutter/material.dart';
import 'src/core/theme/app_theme.dart';
import 'src/core/theme/design_tokens.dart';

void main() {
  runApp(const MetrologyApp());
}

class MetrologyApp extends StatelessWidget {
  const MetrologyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MetrologyAI Mobile',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MetrologyAI — Field LMO'),
        actions: const [
          Padding(
            padding: EdgeInsets.symmetric(horizontal: AppSpacing.space2),
            child: Icon(Icons.verified_user, color: AppColors.brass500),
          )
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Legal Metrology Evidence System',
                style: AppTypography.lg,
              ),
              const SizedBox(height: AppSpacing.space1),
              const Text(
                'PCR 2011 Compliance Verification Engine',
                style: AppTypography.xs,
              ),
              const SizedBox(height: AppSpacing.space3),
              // Signature Calibration Tick Rule motif
              Container(
                height: AppConstraints.calibrationTickHeight,
                color: AppColors.brass500,
              ),
              const SizedBox(height: AppSpacing.space3),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.space2),
                  child: Row(
                    children: [
                      const Icon(Icons.shield_outlined, color: AppColors.verdictPass, size: 32),
                      const SizedBox(width: AppSpacing.space2),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Tokens Layer Integrated',
                              style: AppTypography.base.copyWith(fontWeight: FontWeight.bold),
                            ),
                            const Text(
                              'Colors, Typography (§3), and Spacing (§4) imported from design_tokens.dart.',
                              style: AppTypography.xs,
                            ),
                          ],
                        ),
                      )
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
