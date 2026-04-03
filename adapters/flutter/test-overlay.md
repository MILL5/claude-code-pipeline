# Flutter / Dart — Test Overlay

<!-- Injected into test-architect-agent at ADAPTER:TECH_STACK_CONTEXT marker -->

## Test Framework: flutter test

Flutter provides three test levels with increasing scope and cost. Test the architecture layers bottom-up: Services → Repositories → ViewModels → Widgets → Integration flows.

## Test Structure

```
test/
  unit/
    data/
      services/
        feature_service_test.dart
      repositories/
        feature_repository_test.dart
    ui/
      feature_name/
        feature_view_model_test.dart
  widget/
    ui/
      feature_name/
        feature_view_test.dart
  goldens/
    feature_widget_test.dart
integration_test/
  critical_flow_test.dart
```

Naming convention: `test_<feature>_<scenario>_<expected>` for test descriptions.

File naming: `<source_file>_test.dart` in a parallel directory structure under `test/`.

## Unit Tests

Test every method on Services, Repositories, and ViewModels individually.

```dart
import 'package:flutter_test/flutter_test.dart';

void main() {
  late FeatureRepository repository;
  late FakeFeatureService fakeService;

  setUp(() {
    fakeService = FakeFeatureService();
    repository = FeatureRepository(service: fakeService);
  });

  group('FeatureRepository', () {
    test('fetches and transforms data from service', () async {
      fakeService.stubbedResponse = RawData(id: '1', value: 42);

      final result = await repository.getFeature('1');

      expect(result, isA<Ok<Feature>>());
      expect((result as Ok<Feature>).value.id, '1');
    });

    test('returns error result on service failure', () async {
      fakeService.shouldFail = true;

      final result = await repository.getFeature('1');

      expect(result, isA<Error<Feature>>());
    });
  });
}
```

### Mocking Strategy

- Write **fakes** (manual implementations of abstract classes) that focus on inputs/outputs — not implementation details.
- Use `mockito` + `@GenerateNiceMocks` for generated mocks when fakes would be verbose.
- Mock at the boundary: fake Services when testing Repositories, fake Repositories when testing ViewModels.
- Never mock the class under test.

### ViewModel Testing

```dart
test('updates state when data loads', () async {
  final viewModel = FeatureViewModel(repository: fakeRepository);

  await viewModel.loadData();

  expect(viewModel.items, hasLength(3));
  expect(viewModel.isLoading, isFalse);
});

test('notifies listeners on state change', () async {
  final viewModel = FeatureViewModel(repository: fakeRepository);
  var notified = false;
  viewModel.addListener(() => notified = true);

  await viewModel.loadData();

  expect(notified, isTrue);
});
```

## Widget Tests

Test widget rendering, user interaction, and child widget instantiation using `testWidgets()`.

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('displays loading indicator while fetching', (tester) async {
    final viewModel = FakeFeatureViewModel(isLoading: true);

    await tester.pumpWidget(
      MaterialApp(
        home: FeatureView(viewModel: viewModel),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('tapping item navigates to detail', (tester) async {
    final viewModel = FakeFeatureViewModel(items: [testItem]);

    await tester.pumpWidget(
      MaterialApp(
        home: FeatureView(viewModel: viewModel),
      ),
    );

    await tester.tap(find.text(testItem.title));
    await tester.pumpAndSettle();

    expect(find.byType(DetailView), findsOneWidget);
  });
}
```

### Key Widget Test APIs

- `tester.pumpWidget(widget)` — Renders the widget.
- `tester.pump(duration)` — Advances time by duration, triggers rebuild.
- `tester.pumpAndSettle()` — Pumps until all animations complete.
- `tester.tap(finder)` — Simulates tap on found widget.
- `tester.enterText(finder, text)` — Types text into field.
- `tester.drag(finder, offset)` — Simulates drag gesture.
- `find.byType(Widget)` — Finds by widget type.
- `find.text('string')` — Finds by displayed text.
- `find.byKey(Key('id'))` — Finds by widget key.
- Wrap in `MaterialApp` or `CupertinoApp` for theming/navigation context.

## Golden Tests

Verify widget rendering matches reference bitmap images.

```dart
testWidgets('feature widget matches golden', (tester) async {
  await tester.pumpWidget(
    MaterialApp(home: FeatureWidget(data: testData)),
  );

  await expectLater(
    find.byType(FeatureWidget),
    matchesGoldenFile('goldens/feature_widget.png'),
  );
});
```

Update golden files: `flutter test --update-goldens`

Golden tests are brittle across platforms/OS versions. Run on CI with a fixed environment. Store golden files in `test/goldens/`.

## Integration Tests

Test critical user journeys end-to-end on real devices or emulators.

```dart
// integration_test/app_test.dart
import 'package:integration_test/integration_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:my_app/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('complete feature flow', (tester) async {
    app.main();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Get Started'));
    await tester.pumpAndSettle();

    expect(find.text('Welcome'), findsOneWidget);
  });
}
```

## Coverage

```bash
flutter test --coverage                          # Generates coverage/lcov.info
# Convert to HTML (requires lcov):
genhtml coverage/lcov.info -o coverage/html
```

### Coverage Exclusions

Exclude from coverage calculations:
- Generated files: `*.g.dart`, `*.freezed.dart`, `*.gen.dart`
- L10n generated: `lib/l10n/`, `*.arb`
- Platform-specific: `android/`, `ios/`, `linux/`, `macos/`, `windows/`, `web/`
- Config: `pubspec.yaml`, `analysis_options.yaml`

## Async Testing

- Use `async` test bodies for `Future`-based code.
- `tester.pump()` advances the event loop — use after triggering async operations in widget tests.
- `tester.pumpAndSettle()` waits for all animations and scheduled frames.
- `tester.runAsync(() async { ... })` for real async operations (HTTP, file I/O) in widget tests.
- For `Stream`-based code, use `expectLater(stream, emitsInOrder([...]))`.

## Anti-Patterns

- **Testing implementation details:** Don't assert on internal state — test observable behavior (rendered UI, emitted values, returned results).
- **Shared mutable state between tests:** Each test must set up its own fakes/state in `setUp()`.
- **Testing framework code:** Don't test that `Navigator` works or that `provider` propagates — test your code's behavior.
- **Hard-coded delays:** Never use `Future.delayed` in tests. Use `tester.pump(duration)` for animations, `tester.pumpAndSettle()` for completion.
- **Testing generated code:** Don't write tests for `*.g.dart` or `*.freezed.dart` output.
- **Broad golden tests:** Golden-test small, isolated widgets — not full screens that change frequently.
- **Missing tearDown:** If a test registers global error handlers or modifies static state, restore in `tearDown()`.
