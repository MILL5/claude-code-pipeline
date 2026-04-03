# Android / Kotlin Adapter

## Stack Metadata

- **Stack name:** `android`
- **Display name:** Android / Kotlin
- **Languages:** Kotlin (primary), Java (legacy)
- **Build system:** Gradle (Kotlin DSL preferred) + Android Gradle Plugin (AGP)
- **Test framework:** JUnit 4 + Robolectric (local), Espresso / Compose Testing (instrumented)
- **Coverage tool:** JaCoCo
- **Dependency injection:** Hilt

## Build & Test Commands

- **Build:** `python3 .claude/scripts/android/build.py [--project-dir .] [--module app] [--variant debug]`
- **Test:** `python3 .claude/scripts/android/test.py [--project-dir .] [--module app] [--variant debug] [--no-coverage]`

## Blocked Commands

These commands are blocked by hooks and must use the pipeline skills instead:
- `./gradlew test` / `./gradlew connectedAndroidTest` -> use `test-runner` skill
- `./gradlew build` / `./gradlew assemble` / `./gradlew lint` -> use `build-runner` skill
- `gradle` / `gradlew` direct invocations -> use `build-runner` / `test-runner` skill

## Overlay Files

| Overlay | Agent | Purpose |
|---------|-------|---------|
| `architect-overlay.md` | architect-agent | Android architecture layers, Jetpack patterns, complexity mapping |
| `implementer-overlay.md` | implementer-agent | Kotlin style, coroutines, Compose, lifecycle, security |
| `reviewer-overlay.md` | code-reviewer-agent | Android/Kotlin-specific review checklist |
| `test-overlay.md` | test-architect-agent | JUnit, Robolectric, Espresso, Compose testing, Turbine |

## Project Detection

This adapter activates when the project root contains:
- `build.gradle.kts` or `build.gradle` (top-level or in `app/`)

## Common Conventions

- **Architecture:** MVVM — UI Layer (Compose/Views + ViewModel) + Domain Layer (optional Use Cases) + Data Layer (Repository + DataSource)
- **State management:** ViewModel + StateFlow (modern) or LiveData (legacy), sealed classes for UI state
- **DI:** Hilt with constructor injection, `@HiltViewModel`, scoped bindings
- **UI:** Jetpack Compose (recommended for new projects), Material Design 3
- **Navigation:** Navigation Compose with type-safe routes
- **Async:** Kotlin Coroutines with structured concurrency — viewModelScope, lifecycleScope, injected dispatchers
- **Persistence:** Room (database), DataStore (preferences), EncryptedSharedPreferences (secrets)
- **Kotlin style:** lowerCamelCase functions/properties, UpperCamelCase classes, SCREAMING_SNAKE_CASE constants, `val` over `var`, immutable collections
- **Error handling:** Sealed Result types, specific exception catching, never catch CancellationException
- **Background work:** WorkManager for persistent tasks, coroutines for in-process async
