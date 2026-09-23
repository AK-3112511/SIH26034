import 'package:flutter/material.dart';
import '../../../core/config/app_config.dart';
import '../../../core/theme/design_tokens.dart';
import '../../../core/widgets/calibration_tick_rule.dart';
import '../../scans/presentation/home_screen.dart';
import '../data/auth_service.dart';

/// Login Screen (Mobile UX §2, Screen 1)
///
/// Authentic government instrumentation aesthetic for Legal Metrology Officers.
/// Auth via official government credential hitting backend /auth/login.
class LoginScreen extends StatefulWidget {
  final AuthService? authService;

  /// When hosted by `AuthGate` the gate swaps the root widget on sign-in, so
  /// this screen must not also push a route. Standalone use (and widget tests)
  /// keeps the default navigation.
  final bool navigateOnSuccess;

  const LoginScreen({
    super.key,
    this.authService,
    this.navigateOnSuccess = true,
  });

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _errorMessage;
  bool _showOfflineNotice = false;

  late final AuthService _auth;

  @override
  void initState() {
    super.initState();
    _auth = widget.authService ?? AuthService();
    // Explain an involuntary return to this screen (expired or revoked token)
    // rather than leaving the officer to guess why they were signed out.
    final reason = _auth.sessionEndedReason;
    if (reason != null) {
      _errorMessage = reason;
      _auth.clearSessionEndedReason();
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _showServerConfigDialog() {
    final urlController = TextEditingController(text: AppConfig().baseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.paper000,
        title: const Text('Backend Server Endpoint', style: AppTypography.lg),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Specify the base API URL (e.g. for USB adb reverse, emulator, or local network):',
              style: AppTypography.xs.copyWith(color: AppColors.ink600),
            ),
            const SizedBox(height: AppSpacing.space2),
            TextField(
              controller: urlController,
              style: AppTypography.base.copyWith(color: AppColors.ink900),
              decoration: const InputDecoration(
                labelText: 'API BASE URL',
                hintText: 'http://127.0.0.1:8000/api/v1',
              ),
            ),
            const SizedBox(height: AppSpacing.space1),
            Text(
              'USB Device: Run "adb reverse tcp:8000 tcp:8000"\nEmulator: Use "http://10.0.2.2:8000/api/v1"',
              style: AppTypography.dataMono.copyWith(fontSize: 11.0, color: AppColors.ink600),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('CANCEL'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              minimumSize: const Size(100, 40),
            ),
            onPressed: () async {
              final error = await AppConfig().setBaseUrl(urlController.text);
              if (!ctx.mounted) return;
              if (error != null) {
                ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(error)));
                return;
              }
              Navigator.of(ctx).pop();
              if (mounted) setState(() {});
            },
            child: const Text('SAVE'),
          ),
        ],
      ),
    );
  }

  Future<void> _handleLogin() async {
    setState(() {
      _errorMessage = null;
      _showOfflineNotice = false;
    });

    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
    });

    final result = await _auth.login(
      username: _usernameController.text,
      password: _passwordController.text,
    );

    if (!mounted) return;

    setState(() {
      _isLoading = false;
    });

    if (result.isSuccess) {
      if (widget.navigateOnSuccess) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => const HomeScreen(),
          ),
        );
      }
    } else {
      setState(() {
        _errorMessage = result.errorMessage ?? 'Authentication failed';
        if (result.isNetworkError) {
          _showOfflineNotice = true;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.paper100,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppConstraints.mobileScreenMargin),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: AppSpacing.space3),

                // Official Department Emblem & Header
                Row(
                  children: [
                    Container(
                      width: 44.0,
                      height: 44.0,
                      decoration: BoxDecoration(
                        color: AppColors.ink900,
                        borderRadius: BorderRadius.circular(AppRadius.card),
                      ),
                      child: const Icon(
                        Icons.shield_outlined,
                        color: AppColors.brass500,
                        size: 26.0,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.space2),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'LEGAL METROLOGY DIVISION',
                            style: AppTypography.xs.copyWith(
                              color: AppColors.ink600,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 0.8,
                            ),
                          ),
                          const Text(
                            'MetrologyAI Mobile',
                            style: AppTypography.xl,
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Server Connection Settings',
                      icon: const Icon(
                        Icons.settings_ethernet,
                        color: AppColors.ink600,
                        size: 22.0,
                      ),
                      onPressed: _showServerConfigDialog,
                    ),
                  ],
                ),

                const SizedBox(height: AppSpacing.space1),
                Text(
                  'PCR 2011 Field Inspection & Evidence System',
                  style: AppTypography.xs.copyWith(color: AppColors.ink600),
                ),

                // Signature Calibration Tick Rule divider
                const CalibrationTickRule(),

                // Offline notice. Informational only: there is no way past
                // this screen without credentials the server has accepted, so
                // captures can always be attributed to a real officer.
                if (_showOfflineNotice) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(AppSpacing.space2),
                    decoration: BoxDecoration(
                      color: AppColors.paper000,
                      borderRadius: BorderRadius.circular(AppRadius.card),
                      border: Border.all(
                        color: AppColors.verdictPending,
                        width: 1.0,
                      ),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(
                          Icons.wifi_off_outlined,
                          color: AppColors.verdictPending,
                          size: 20.0,
                        ),
                        const SizedBox(width: AppSpacing.space1),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'SERVER UNREACHABLE',
                                style: AppTypography.xs.copyWith(
                                  color: AppColors.verdictPending,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: AppSpacing.space05),
                              Text(
                                'Check the server address below and your network. '
                                'Once you have signed in on this device, you can keep '
                                'capturing offline and everything uploads when you '
                                'are back in range.',
                                style: AppTypography.xs.copyWith(
                                  color: AppColors.ink900,
                                ),
                              ),
                              const SizedBox(height: AppSpacing.space1),
                              OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: AppColors.ink900,
                                  side: const BorderSide(color: AppColors.ink600),
                                  minimumSize: const Size(160, 48),
                                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.space1),
                                ),
                                icon: const Icon(Icons.dns_outlined, size: 16.0),
                                label: Text(
                                  'CHANGE SERVER ADDRESS',
                                  style: AppTypography.xs.copyWith(
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.ink900,
                                  ),
                                ),
                                onPressed: _showServerConfigDialog,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.space2),
                ],

                // Authentication Card
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.space2),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'LMO Credential Login',
                          style: AppTypography.lg,
                        ),
                        const SizedBox(height: AppSpacing.space05),
                        Text(
                          'Sign in using your assigned government officer identifier to access field capture mode.',
                          style: AppTypography.xs.copyWith(color: AppColors.ink600),
                        ),
                        const SizedBox(height: AppSpacing.space3),

                        // Form Field 1: Username / Email
                        // §5.6: Label above field (never placeholder-as-label)
                        Text(
                          'OFFICIAL USERNAME OR EMAIL',
                          style: AppTypography.xs.copyWith(
                            color: AppColors.ink600,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.space1),
                        TextFormField(
                          controller: _usernameController,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          style: AppTypography.base.copyWith(color: AppColors.ink900),
                          decoration: const InputDecoration(
                            hintText: 'e.g. officer_username or name@gov.in',
                            prefixIcon: Icon(
                              Icons.badge_outlined,
                              color: AppColors.ink600,
                              size: 20.0,
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.trim().isEmpty) {
                              return 'Officer username or email is required';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: AppSpacing.space2),

                        // Form Field 2: Password
                        // §5.6: Label above field
                        Text(
                          'SECURITY CREDENTIAL / PASSWORD',
                          style: AppTypography.xs.copyWith(
                            color: AppColors.ink600,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.space1),
                        TextFormField(
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          textInputAction: TextInputAction.done,
                          onFieldSubmitted: (_) => _handleLogin(),
                          style: AppTypography.base.copyWith(color: AppColors.ink900),
                          decoration: InputDecoration(
                            hintText: 'Enter secure password',
                            prefixIcon: const Icon(
                              Icons.lock_outline,
                              color: AppColors.ink600,
                              size: 20.0,
                            ),
                            suffixIcon: IconButton(
                              icon: Icon(
                                _obscurePassword
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined,
                                color: AppColors.ink600,
                                size: 20.0,
                              ),
                              onPressed: () {
                                setState(() {
                                  _obscurePassword = !_obscurePassword;
                                });
                              },
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Security password is required';
                            }
                            return null;
                          },
                        ),

                        // Error Message Display
                        if (_errorMessage != null) ...[
                          const SizedBox(height: AppSpacing.space2),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(AppSpacing.space1),
                            decoration: BoxDecoration(
                              color: AppColors.verdictFail.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(AppRadius.card),
                              border: Border.all(
                                color: AppColors.verdictFail,
                                width: 1.0,
                              ),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.error_outline,
                                  color: AppColors.verdictFail,
                                  size: 18.0,
                                ),
                                const SizedBox(width: AppSpacing.space1),
                                Expanded(
                                  child: Text(
                                    _errorMessage!,
                                    style: AppTypography.xs.copyWith(
                                      color: AppColors.verdictFail,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],

                        const SizedBox(height: AppSpacing.space3),

                        // Primary Action Button (§5.2: ink-900 fill, 48px min height)
                        ElevatedButton(
                          onPressed: _isLoading ? null : _handleLogin,
                          child: _isLoading
                              ? const SizedBox(
                                  height: 20.0,
                                  width: 20.0,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.0,
                                    color: AppColors.paper000,
                                  ),
                                )
                              : const Text('AUTHENTICATE & ENTER FIELD MODE'),
                        ),

                      ],
                    ),
                  ),
                ),

                const SizedBox(height: AppSpacing.space4),

                // System Footer
                Center(
                  child: Column(
                    children: [
                      Text(
                        'MetrologyAI Engine v0.1.0 • Standards Enforcement',
                        style: AppTypography.dataMono.copyWith(
                          fontSize: 12.0,
                          color: AppColors.ink600,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.space05),
                      Text(
                        'All authentication and field activities are recorded to the append-only audit trail.',
                        textAlign: TextAlign.center,
                        style: AppTypography.xs.copyWith(
                          color: AppColors.ink600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
