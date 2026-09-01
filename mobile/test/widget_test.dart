import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart';

void main() {
  testWidgets('MetrologyApp smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const MetrologyApp());
    expect(find.text('MetrologyAI — Field LMO'), findsOneWidget);
  });
}
