import 'dart:async';

import 'package:flutter/material.dart';

import 'src/core/config/app_config.dart';
import 'src/core/theme/app_theme.dart';
import 'src/features/auth/data/auth_service.dart';
import 'src/features/auth/presentation/login_screen.dart';
import 'src/features/notifications/services/local_notification_service.dart';
import 'src/features/notifications/services/notification_service.dart';
import 'src/features/scans/presentation/home_screen.dart';
import 'src/features/scans/services/sync_worker.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Server address and the stable device id must exist before anything makes a
  // request or writes an evidence hash.
  await AppConfig().load();

  // Set up the notification channel before any verdict can arrive.
  await LocalNotificationService().initialize();

  // Resume a previous session so an officer who was signed in yesterday is not
  // sent back to a login screen at the start of a shift.
  await AuthService().restoreSession();

  await NotificationService().loadPersisted();

  // A capture stranded mid-upload by a force-stop is re-queued before the first
  // sync pass, so it is never silently lost.
  unawaited(SyncWorker().recoverOrphanedUploads());
  unawaited(SyncWorker().initializeWorkManager());

  runApp(const MetrologyApp());
}

class MetrologyApp extends StatelessWidget {
  /// Overrides the root screen. Used by tests to mount a single screen without
  /// going through the auth gate.
  final Widget? home;

  const MetrologyApp({
    super.key,
    this.home,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MetrologyAI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: home ?? const AuthGate(),
    );
  }
}

/// Chooses between the login screen and the app based on live auth state.
///
/// Listening rather than navigating means a 401 anywhere - a background upload,
/// an event poll - drops the officer straight back to login, instead of leaving
/// them on a screen whose every request is silently failing.
class AuthGate extends StatefulWidget {
  final AuthService? authService;

  const AuthGate({super.key, this.authService});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  late final AuthService _auth;

  @override
  void initState() {
    super.initState();
    _auth = widget.authService ?? AuthService();
    _auth.addListener(_onAuthChanged);
  }

  @override
  void dispose() {
    _auth.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return _auth.isAuthenticated
        ? const HomeScreen()
        : const LoginScreen(navigateOnSuccess: false);
  }
}
