# Flutter / Dart Adapter

## Stack Metadata

- **Stack name:** `flutter`
- **Display name:** Flutter / Dart
- **Languages:** Dart
- **Build system:** Flutter SDK (`flutter analyze`, `dart format`)
- **Test framework:** `flutter test` (unit, widget, integration, golden)
- **Coverage tool:** `flutter test --coverage` (lcov)
- **Code generation:** `build_runner` + `freezed` + `json_serializable`

## Build & Test Commands

- **Build:** `python3 .claude/scripts/flutter/build.py [--project-dir .] [--no-format-check]`
- **Test:** `python3 .claude/scripts/flutter/test.py [--project-dir .] [--no-coverage] [--exclude-from-coverage '<pattern>']`

## Blocked Commands

These commands are blocked by hooks and must use the pipeline skills instead:
- `flutter test` / `flutter analyze` / `dart analyze` -> use `build-runner` / `test-runner` skill
- `flutter build` / `flutter run` -> use `build-runner` skill
- `dart run build_runner` -> use `build-runner` skill

## Overlay Files

| Overlay | Agent | Purpose |
|---------|-------|---------|
| `architect-overlay.md` | architect-agent | MVVM architecture, widget decomposition, state management patterns |
| `implementer-overlay.md` | implementer-agent | Dart style, Flutter composition, performance, accessibility |
| `reviewer-overlay.md` | code-reviewer-agent | Flutter/Dart-specific review checklist |
| `test-overlay.md` | test-architect-agent | flutter test, widget tests, golden tests, integration tests |

## Project Detection

This adapter activates when the project root contains:
- `pubspec.yaml` with `flutter:` section

## Common Conventions

- **Architecture:** MVVM — View (widgets) + ViewModel (ChangeNotifier) + Repository + Service layers
- **State management:** ChangeNotifier + provider (Google-recommended); Riverpod or BLoC for complex cases
- **Navigation:** go_router with declarative routing and deep link support
- **Data models:** Immutable classes via freezed; JSON via json_serializable
- **Styling:** Material 3 (default), Cupertino for iOS-native fidelity, adaptive constructors for cross-platform
- **Dart style:** Effective Dart — lowerCamelCase, `///` doc comments, `async`/`await`, `final` fields
- **L10n:** flutter_localizations + gen-l10n with ARB files — no hard-coded user-facing strings
- **Error handling:** Result pattern at service boundaries; FlutterError.onError + PlatformDispatcher for global handling
- **Accessibility:** 4.5:1 contrast, 48x48 tap targets, Semantics widget for custom interactive elements
