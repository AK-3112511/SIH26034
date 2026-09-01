import 'package:flutter/material.dart';
import 'src/core/theme/app_theme.dart';
import 'src/features/auth/presentation/login_screen.dart';

void main() {
  runApp(const MetrologyApp());
}

class MetrologyApp extends StatelessWidget {
  final Widget? home;

  const MetrologyApp({
    super.key,
    this.home,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MetrologyAI Mobile',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: home ?? const LoginScreen(),
    );
  }
}
