import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/src/core/theme/app_theme.dart';
import 'package:mobile/src/core/widgets/status_chip.dart';
import 'package:mobile/src/core/widgets/verdict_seal_badge.dart';
import 'package:mobile/src/features/scans/models/capture_record.dart';
import 'package:mobile/src/features/scans/presentation/scan_detail_screen.dart';

CaptureRecord _record({
  String? serverStatus,
  String? summary,
  List<String> failures = const [],
  String syncStatus = 'SYNCED',
  String? lastError,
}) {
  return CaptureRecord(
    localId: 'loc-1',
    lat: 13.0827,
    lng: 80.2707,
    accuracyMetres: 7.4,
    capturedAtUtc: DateTime.utc(2026, 9, 22, 10, 30).toIso8601String(),
    referenceObjectType: 'debit_card',
    productType: 'box',
    productName: 'Golden Crunch Biscuits',
    syncStatus: syncStatus,
    serverScanId: 'scan-abc',
    serverStatus: serverStatus,
    verdictSummary: summary,
    ruleFailuresJson: failures.isEmpty ? null : jsonEncode(failures),
    lastError: lastError,
  );
}

Future<void> _pump(WidgetTester tester, CaptureRecord record) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.lightTheme,
      home: ScanDetailScreen(localId: record.localId, initialRecord: record),
    ),
  );
  await tester.pump();
}

void main() {
  group('ScanDetailScreen', () {
    testWidgets('shows a non-compliant verdict with the rules in plain language',
        (tester) async {
      await _pump(
        tester,
        _record(
          serverStatus: 'FAILED',
          summary: 'Failed 2 rules: 6.1.e, schedule_ii.',
          failures: ['6.1.e', 'schedule_ii'],
        ),
      );

      expect(find.text('Non-compliant'), findsOneWidget);
      expect(find.byType(VerdictSealBadge), findsOneWidget);
      expect(find.text('Declarations in breach'), findsOneWidget);

      // An officer reading this in a shop should not have to decode rule ids.
      expect(
        find.text('Rule 6(1)(e) - Retail sale price, inclusive of all taxes'),
        findsOneWidget,
      );
      expect(
        find.text('Rule 7(3) / Schedule II - Minimum height of the declaration'),
        findsOneWidget,
      );
    });

    testWidgets('still reads as law for a row written by an older build',
        (tester) async {
      await _pump(
        tester,
        _record(
          serverStatus: 'FAILED',
          summary: 'Failed 1 rule.',
          failures: ['rule_6_1_e'],
        ),
      );

      expect(
        find.text('Rule 6(1)(e) - Retail sale price, inclusive of all taxes'),
        findsOneWidget,
      );
    });

    testWidgets('shows evidence provenance for the capture', (tester) async {
      await _pump(tester, _record(serverStatus: 'PASSED', summary: 'All verified.'));

      expect(find.text('Compliant'), findsOneWidget);
      expect(find.text('Evidence record'), findsOneWidget);
      expect(find.text('Golden Crunch Biscuits'), findsOneWidget);
      expect(find.textContaining('13.08270, 80.27070'), findsOneWidget);
      expect(find.textContaining('+/-7 m'), findsOneWidget);
      expect(find.text('debit card'), findsOneWidget);

      // Nothing breached, so there is no breach section to show.
      expect(find.text('Declarations in breach'), findsNothing);
    });

    testWidgets('an uploaded scan without a verdict says it is still being assessed',
        (tester) async {
      await _pump(tester, _record());

      expect(find.text('Awaiting verdict'), findsOneWidget);
      expect(find.textContaining('still assessing it'), findsOneWidget);
    });

    testWidgets('a queued capture explains it has not been sent yet', (tester) async {
      await _pump(
        tester,
        _record(
          syncStatus: 'FAILED',
          lastError: 'No connection to the server.',
        ),
      );

      // Sync state and verdict are separate signals and both are shown.
      expect(find.byType(StatusChip), findsOneWidget);
      expect(find.text('Upload failed'), findsOneWidget);
      expect(find.textContaining('has not been uploaded yet'), findsOneWidget);
      expect(find.text('No connection to the server.'), findsOneWidget);
    });
  });
}
