import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../../core/config/app_config.dart';
import '../../../core/theme/design_tokens.dart';
import '../../auth/data/auth_service.dart';
import '../../scans/services/sync_worker.dart';

/// Profile and Settings.
///
/// Also the only place an officer can point the app at a different server,
/// which matters because the API host is a LAN address that differs per site
/// and was previously only changeable by rebuilding the app.
class SettingsScreen extends StatefulWidget {
  final AuthService? authService;
  final AppConfig? appConfig;
  final SyncWorker? syncWorker;

  const SettingsScreen({
    super.key,
    this.authService,
    this.appConfig,
    this.syncWorker,
  });

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final AuthService _auth;
  late final AppConfig _config;
  late final SyncWorker _syncWorker;
  late final TextEditingController _baseUrlController;

  String? _baseUrlError;
  String _version = '';
  bool _savingUrl = false;

  @override
  void initState() {
    super.initState();
    _auth = widget.authService ?? AuthService();
    _config = widget.appConfig ?? AppConfig();
    _syncWorker = widget.syncWorker ?? SyncWorker();
    _baseUrlController = TextEditingController(text: _config.baseUrl);
    _loadVersion();
  }

  @override
  void dispose() {
    _baseUrlController.dispose();
    super.dispose();
  }

  Future<void> _loadVersion() async {
    try {
      final info = await PackageInfo.fromPlatform();
      if (!mounted) return;
      setState(() => _version = '${info.version} (${info.buildNumber})');
    } catch (e) {
      debugPrint('[Settings] Could not read package info: $e');
    }
  }

  Future<void> _saveBaseUrl() async {
    setState(() {
      _savingUrl = true;
      _baseUrlError = null;
    });

    final error = await _config.setBaseUrl(_baseUrlController.text);

    if (!mounted) return;
    setState(() {
      _savingUrl = false;
      _baseUrlError = error;
      if (error == null) _baseUrlController.text = _config.baseUrl;
    });

    if (error == null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Server address saved.')),
      );
    }
  }

  Future<void> _setWifiOnly(bool value) async {
    await _config.setWifiOnlySync(value);
    // Re-register the job so the network constraint actually changes, rather
    // than only the switch position.
    await _syncWorker.registerPeriodicSync();
    if (mounted) setState(() {});
  }

  Future<void> _confirmLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text(
          'Captures waiting to upload stay on this device, but they cannot be '
          'sent until you sign in again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await _auth.logout();
      // The AuthGate at the root swaps to the login screen on this change, so
      // there is no navigation to do here.
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = _auth.currentUser;

    return Scaffold(
      backgroundColor: AppColors.paper100,
      appBar: AppBar(
        backgroundColor: AppColors.ink900,
        foregroundColor: AppColors.paper000,
        title: Text(
          'Profile & settings',
          style: AppTypography.base.copyWith(
            color: AppColors.paper000,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
        children: [
          _section(
            'Officer',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _row('Name', user?.fullName ?? 'Not signed in'),
                _row('Username', user?.username ?? '-'),
                _row('Role', _roleLabel(user?.role)),
                _row('District', user?.district ?? '-'),
                if (_auth.isOffline)
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.space1),
                    child: Text(
                      'Working from a cached session. Uploads resume when the server is reachable.',
                      style: AppTypography.xs.copyWith(color: AppColors.verdictPending),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.space2),
          _section(
            'Server',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _baseUrlController,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  decoration: InputDecoration(
                    labelText: 'API address',
                    helperText: 'For example 192.168.1.7:8000',
                    errorText: _baseUrlError,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AppRadius.card),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.space1),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton(
                    onPressed: _savingUrl ? null : _saveBaseUrl,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppColors.ink900,
                      minimumSize: const Size(0, 48),
                    ),
                    child: Text(_savingUrl ? 'Saving...' : 'Save address'),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.space2),
          _section(
            'Sync',
            Column(
              children: [
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _config.wifiOnlySync,
                  onChanged: _setWifiOnly,
                  title: Text(
                    'Upload on Wi-Fi only',
                    style: AppTypography.base.copyWith(color: AppColors.ink900),
                  ),
                  subtitle: Text(
                    'Evidence photos are large. On mobile data, captures stay queued until Wi-Fi is available.',
                    style: AppTypography.xs.copyWith(color: AppColors.ink600),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.space2),
          _section(
            'About',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _row('App version', _version.isEmpty ? '-' : _version),
                _row('Device ID', _config.deviceId.isEmpty ? '-' : _config.deviceId),
                const SizedBox(height: AppSpacing.space05),
                Text(
                  'The device ID is part of every evidence hash, so it stays fixed for this installation.',
                  style: AppTypography.xs.copyWith(color: AppColors.ink600),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.space3),
          OutlinedButton.icon(
            onPressed: _confirmLogout,
            icon: const Icon(Icons.logout, size: 18),
            label: const Text('Sign out'),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(0, 48),
              foregroundColor: AppColors.verdictFail,
              side: const BorderSide(color: AppColors.verdictFail),
            ),
          ),
          const SizedBox(height: AppSpacing.space3),
        ],
      ),
    );
  }

  static String _roleLabel(String? role) {
    switch (role) {
      case 'field_lmo':
        return 'Field Legal Metrology Officer';
      case 'senior_lmo':
        return 'Senior Legal Metrology Officer';
      case 'admin':
        return 'Administrator';
      default:
        return role ?? '-';
    }
  }

  Widget _section(String title, Widget child) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.space2),
      decoration: BoxDecoration(
        color: AppColors.paper000,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.ink600.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title.toUpperCase(),
            style: AppTypography.xs.copyWith(
              color: AppColors.ink600,
              letterSpacing: 1.0,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: AppSpacing.space1),
          child,
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.space1),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(label, style: AppTypography.xs.copyWith(color: AppColors.ink600)),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.xs.copyWith(
                color: AppColors.ink900,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
