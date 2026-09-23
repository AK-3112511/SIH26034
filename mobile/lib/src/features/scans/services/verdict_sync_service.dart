import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../../../core/constants/api_constants.dart';
import '../../../core/database/database_helper.dart';
import '../../auth/data/auth_service.dart';
import '../models/capture_record.dart';

/// Pulls the compliance verdict back down for captures this device uploaded.
///
/// Without this the officer uploads evidence and never learns what the system
/// concluded: the dashboard has the answer, the handset does not. Each synced
/// capture is polled until the backend reaches a terminal status, then the
/// verdict and the failing rule ids are written into the local row so Home and
/// Scan Detail work offline afterwards.
class VerdictSyncService extends ChangeNotifier {
  static final VerdictSyncService _instance = VerdictSyncService._internal();
  factory VerdictSyncService() => _instance;

  @visibleForTesting
  factory VerdictSyncService.createTestInstance({
    http.Client? client,
    DatabaseHelper? dbHelper,
    AuthService? authService,
  }) {
    return VerdictSyncService._internal(
      client: client,
      dbHelper: dbHelper,
      authService: authService,
    );
  }

  VerdictSyncService._internal({
    http.Client? client,
    DatabaseHelper? dbHelper,
    AuthService? authService,
  })  : _client = client ?? http.Client(),
        _dbHelper = dbHelper ?? DatabaseHelper(),
        _authService = authService ?? AuthService();

  http.Client _client;
  DatabaseHelper _dbHelper;
  AuthService _authService;

  Timer? _timer;
  bool _isRunning = false;

  bool get isRunning => _isRunning;

  @visibleForTesting
  void setDependencies({
    http.Client? client,
    DatabaseHelper? dbHelper,
    AuthService? authService,
  }) {
    if (client != null) _client = client;
    if (dbHelper != null) _dbHelper = dbHelper;
    if (authService != null) _authService = authService;
  }

  /// Begin periodic refresh while the app is in the foreground.
  void start({Duration interval = const Duration(seconds: 25)}) {
    if (_isRunning) return;
    _isRunning = true;
    notifyListeners();
    unawaited(refreshOnce());
    _timer = Timer.periodic(interval, (_) => unawaited(refreshOnce()));
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
    if (_isRunning) {
      _isRunning = false;
      notifyListeners();
    }
  }

  /// Ask the backend about every capture still waiting on a verdict.
  /// Returns how many rows changed, so callers can avoid a pointless rebuild.
  Future<int> refreshOnce() async {
    if (!_authService.isAuthenticated) return 0;

    List<CaptureRecord> pending;
    try {
      pending = await _dbHelper.getCapturesAwaitingVerdict();
    } catch (e) {
      debugPrint('[VerdictSyncService] Could not read pending captures: $e');
      return 0;
    }
    if (pending.isEmpty) return 0;

    var updated = 0;
    for (final capture in pending) {
      final scanId = capture.serverScanId;
      if (scanId == null || scanId.isEmpty || scanId.startsWith('ACK-')) continue;

      try {
        final response = await _client.get(
          Uri.parse(ApiConstants.scanDetailEndpoint(scanId)),
          headers: {'Accept': 'application/json', ..._authService.authHeaders},
        ).timeout(const Duration(seconds: 10));

        if (response.statusCode == 401) {
          await _authService.handleUnauthorized();
          return updated;
        }
        if (response.statusCode != 200) {
          debugPrint('[VerdictSyncService] Scan $scanId returned HTTP ${response.statusCode}');
          continue;
        }

        final body = jsonDecode(response.body) as Map<String, dynamic>;
        final status = body['status']?.toString();
        if (status == null || status == capture.serverStatus) continue;

        final failures = _failingRuleIds(body['rule_results']);
        await _dbHelper.updateServerVerdict(
          localId: capture.localId,
          serverStatus: status,
          verdictSummary: _summarise(status, failures, body),
          ruleFailuresJson: jsonEncode(failures),
        );
        updated++;
      } catch (e) {
        debugPrint('[VerdictSyncService] Could not refresh scan $scanId: $e');
      }
    }

    if (updated > 0) notifyListeners();
    return updated;
  }

  List<String> _failingRuleIds(Object? ruleResults) {
    if (ruleResults is! List) return const [];
    return ruleResults
        .whereType<Map<String, dynamic>>()
        .where((r) => r['status']?.toString().toUpperCase() == 'FAIL')
        .map((r) => r['rule_id']?.toString() ?? '')
        .where((id) => id.isNotEmpty)
        .toList();
  }

  /// One line the officer can read on a list tile without opening anything.
  String _summarise(String status, List<String> failures, Map<String, dynamic> body) {
    switch (status.toUpperCase()) {
      case 'PASSED':
        return 'All mandated declarations verified.';
      case 'FAILED':
        if (failures.isEmpty) return 'Declarations did not meet PCR 2011 requirements.';
        return failures.length == 1
            ? 'Failed rule ${failures.first}.'
            : 'Failed ${failures.length} rules: ${failures.join(', ')}.';
      case 'PENDING_REVIEW':
        return 'Sent to a senior officer for manual review.';
      case 'CALIBRATION_FAILED':
      case 'LOW_CONFIDENCE_CALIBRATION':
        return 'The reference card could not be measured reliably. Re-capture with the card flat and fully in frame.';
      case 'PROCESSING_FAILED':
        final reason = body['processing_error']?.toString();
        return reason == null || reason.isEmpty
            ? 'The server could not process this image.'
            : 'Processing error: $reason';
      default:
        return 'Status: $status';
    }
  }

  @override
  void dispose() {
    stop();
    super.dispose();
  }
}
