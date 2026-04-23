# Flutter / Dart — Essential Rules (Haiku)

- Never run `git commit`/`git push` — orchestrator commits after review
- MVVM layers: View (display), ViewModel (ChangeNotifier), Repository, Service
- Extract widgets as classes, not helper functions — `const` constructors everywhere
- `setState` only for ephemeral widget-local state — never high in the tree
- `ListView.builder` for collections — never concrete child lists for dynamic data
- Dispose all controllers, streams, timers, subscriptions in `dispose()`
- Check `mounted` before `setState` after async operations
- No hard-coded user-facing strings — use `AppLocalizations`
- Specific `on ExceptionType` clauses — never bare `catch`
- `final` fields, constructor DI via `provider`, private dependency fields
- `async`/`await` over raw futures, `rethrow` to preserve stack traces
- `compute()` or `Isolate.spawn()` for heavy work — never block the UI thread
- Relative imports within package, `dart:` → `package:` → relative ordering
