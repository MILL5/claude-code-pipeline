# Flutter / Dart — Implementer Overlay

<!-- Injected into implementer-agent at ADAPTER:TECH_STACK_CONTEXT marker -->

## Architecture (MVVM)

- Views display state from their ViewModel — minimal logic (simple conditionals for visibility, animation, layout, routing).
- ViewModels transform repository data into UI state. Expose `Command` objects for user interactions. Store injected dependencies as **private fields**.
- Repositories are the single source of truth per data type. Output domain models, not raw API responses. Handle caching, retry, error transformation.
- Services wrap a single data source (REST endpoint, local storage, platform API). Hold no state. Return `Future` or `Stream`.
- Constructor injection via `provider`. Use `context.read<T>()` to retrieve without rebuilds. No globally accessible singletons or service locators.
- Data flows one direction: Service → Repository → ViewModel → View. User events flow: View → ViewModel → Repository.

## Widget Composition

- **Extract widgets as classes, not helper functions.** Widget classes participate in framework rebuild optimization (same-instance detection skips subtree traversal). Functions do not.
- Mark widgets `const` wherever possible. Enable `prefer_const_constructors` lint.
- One widget, one responsibility. Localize `setState()` to the smallest subtree that actually changes.
- Split build methods >100 lines into smaller widget classes.
- Pass static subtrees as `child` parameter to `AnimatedBuilder` — not inside the builder callback.
- Use `RepaintBoundary` to isolate frequently-redrawn subtrees from their surroundings.

## State Management

- `setState` only for ephemeral, widget-local state (form focus, animation, toggle).
- `ChangeNotifier` + `provider` for app-level state — the Google-recommended approach.
- ViewModels extend `ChangeNotifier`. Each View has exactly one ViewModel.
- Never store computed values — derive them in getters.

## Performance

- No expensive or repetitive work in `build()`. It is called frequently.
- `ListView.builder` / `GridView.builder` for collections — never concrete child lists (`Column(children: [...])`) for dynamic/large data.
- `compute()` or `Isolate.spawn()` for heavy computation (large JSON parsing, image processing). Never block the UI thread.
- Avoid `Opacity` widget in animations — use `AnimatedOpacity` or `FadeInImage`.
- Don't override `operator ==` on widgets — causes O(N^2) behavior and prevents compiler optimizations.
- Frame budget: 16ms at 60Hz (8ms build + 8ms render). 120Hz devices need <8ms total.

## Dart Style (Effective Dart)

- `lowerCamelCase` for variables, functions, parameters, named constants. `UpperCamelCase` for types, extensions, enums, typedefs. `lowercase_with_underscores` for packages, files, import prefixes.
- Capitalize acronyms >2 letters as words (`HttpRequest`, not `HTTPRequest`).
- `///` doc comments on all public APIs. No `//` block comments for documentation.
- Collection literals (`[]`, `{}`) over constructors. `isEmpty`/`isNotEmpty` over `.length == 0`.
- `async`/`await` over raw `Future` chains. `rethrow` to preserve stack traces.
- `final` for fields that don't change. `const` for compile-time constants.
- Initializing formals (`this.parameter`) in constructors.
- `=>` for single-expression members. No `new` keyword.
- `for` loops over `forEach()` with closures. `.toList()` over `List.from()` unless changing type.
- Relative imports within a package. Imports: `dart:` → `package:` → relative, each group alphabetically sorted.

## Null Safety

- Don't explicitly initialize nullable variables to `null` — they're implicitly null.
- Type promotion via null checks (`if (value != null)`) to access non-null members.
- Avoid `late` when you need to check initialization state — use nullable type + null check.
- Don't compare non-nullable booleans to `true`/`false` literals.

## Error Handling

- Result pattern (sealed `Result<T>` with `Ok`/`Error` variants) at service boundaries. Forces exhaustive handling via pattern matching.
- `FlutterError.onError` for framework errors. `PlatformDispatcher.instance.onError` for uncaught async errors. Initialize both in `main()` before `runApp()`.
- Specific `on ExceptionType` clauses — never bare `catch`. Never silently discard errors.
- Check `mounted` before calling `setState` after any async operation.
- Throw `Error` subclasses only for programmatic bugs — never catch them.

## Resource Management

- Dispose **all** controllers and subscriptions in `dispose()`: `AnimationController`, `TextEditingController`, `ScrollController`, `FocusNode`, `StreamSubscription`, `Timer`.
- Cancel async operations in `dispose()` to prevent `setState` after unmount.
- Remove listeners explicitly on objects passed in from outside, even if you call `dispose()`.

## Internationalization

- **No hard-coded user-facing strings.** All text through `AppLocalizations` via `flutter_localizations` + `gen-l10n`.
- ARB files in `lib/l10n/` with `@` metadata descriptions for every translatable string.
- ICU message format for plurals and gendered text. Typed placeholders, not string concatenation.

## Accessibility

- Minimum contrast ratio: 4.5:1 between controls/text and background.
- Minimum tap target size: 48x48 pixels.
- `Semantics` widget with `SemanticsRole` for custom interactive widgets.
- Test with TalkBack (Android) and VoiceOver (iOS).
- Standard Flutter widgets handle accessibility automatically — prefer them over custom implementations.
