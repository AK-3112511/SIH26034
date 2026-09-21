import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../../../core/constants/api_constants.dart';
import '../../auth/data/auth_service.dart';
import '../models/app_event.dart';

/// Real-Time Event Polling Service (§6.2 UX Integration Blueprint)
///
/// Implements the 15–30s polling fallback channel for mobile field officers.
/// Polls GET /api/v1/events/poll with incremental 'since' timestamps.
/// Dispatches incoming `scan.status_changed` and `task.assigned` events
/// to both a broadcast Stream and ChangeNotifier listeners.
class EventPollingService extends ChangeNotifier {
  static final EventPollingService _instance = EventPollingService._internal();
  factory EventPollingService() => _instance;

  @visibleForTesting
  factory EventPollingService.createTestInstance({
    http.Client? client,
    AuthService? authService,
    Duration? pollInterval,
  }) {
    return EventPollingService._internal(
      client: client,
      authService: authService,
      pollInterval: pollInterval,
    );
  }

  EventPollingService._internal({
    http.Client? client,
    AuthService? authService,
    Duration? pollInterval,
  })  : _client = client ?? http.Client(),
        _authService = authService ?? AuthService(),
        _pollInterval = pollInterval ?? const Duration(seconds: 20);

  http.Client _client;
  AuthService _authService;
  Duration _pollInterval;

  Timer? _pollingTimer;
  bool _isPolling = false;
  String? _lastPollTime;
  final List<AppEvent> _receivedEvents = [];
  final StreamController<AppEvent> _eventStreamController =
      StreamController<AppEvent>.broadcast();

  bool get isPolling => _isPolling;
  String? get lastPollTime => _lastPollTime;
  List<AppEvent> get receivedEvents => List.unmodifiable(_receivedEvents);
  Stream<AppEvent> get eventStream => _eventStreamController.stream;

  @visibleForTesting
  void setDependencies({http.Client? client, AuthService? authService}) {
    if (client != null) _client = client;
    if (authService != null) _authService = authService;
  }

  @visibleForTesting
  void setLastPollTime(String? time) {
    _lastPollTime = time;
  }

  /// Start periodic background polling loop per §6.2 (15–30s interval)
  void startPolling({Duration? interval}) {
    if (_isPolling) return;
    if (interval != null) _pollInterval = interval;

    _isPolling = true;
    notifyListeners();

    // Trigger immediate first check, then recurring timer
    pollOnce();
    _pollingTimer = Timer.periodic(_pollInterval, (_) {
      pollOnce();
    });
  }

  /// Stop polling loop (e.g. when app is backgrounded or user logs out)
  void stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
    _isPolling = false;
    notifyListeners();
  }

  /// Perform a single poll request against /api/v1/events/poll
  Future<List<AppEvent>> pollOnce() async {
    final token = _authService.currentToken?.accessToken;
    final headers = <String, String>{
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };

    final queryParams = <String, String>{};
    if (_lastPollTime != null && _lastPollTime!.isNotEmpty) {
      queryParams['since'] = _lastPollTime!;
    }

    final baseUri = Uri.parse(ApiConstants.eventsPollEndpoint);
    final uri = queryParams.isEmpty
        ? baseUri
        : baseUri.replace(queryParameters: queryParams);

    try {
      final response = await _client.get(uri, headers: headers).timeout(
            const Duration(seconds: 10),
          );

      if (response.statusCode == 200) {
        final Map<String, dynamic> data =
            jsonDecode(response.body) as Map<String, dynamic>;

        // Update lastPollTime cursor from server_time
        if (data.containsKey('server_time') && data['server_time'] != null) {
          _lastPollTime = data['server_time'].toString();
        }

        final rawEvents = data['events'];
        final List<AppEvent> newEvents = [];
        if (rawEvents is List) {
          for (final item in rawEvents) {
            if (item is Map<String, dynamic>) {
              final event = AppEvent.fromJson(item);
              newEvents.add(event);
              _receivedEvents.add(event);
              if (!_eventStreamController.isClosed) {
                _eventStreamController.add(event);
              }
            }
          }
        }

        if (newEvents.isNotEmpty) {
          notifyListeners();
        }

        return newEvents;
      } else {
        debugPrint(
            '[EventPollingService] Polling returned HTTP ${response.statusCode}: ${response.body}');
        return [];
      }
    } catch (e) {
      debugPrint('[EventPollingService] Polling error: $e');
      return [];
    }
  }

  @override
  void dispose() {
    stopPolling();
    _eventStreamController.close();
    super.dispose();
  }
}
