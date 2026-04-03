# Android / Kotlin — Architect Overlay

<!-- Injected into architect-agent at ADAPTER:TECH_STACK_CONTEXT marker -->

## Architecture: Google's Recommended Android App Architecture

**UI Layer:** UI elements (Compose or Views) + State holders (ViewModels). ViewModel survives configuration changes, exposes immutable UI state via `StateFlow`. UI state defined as immutable `data class`. Unidirectional data flow: state flows down, events flow up.

**Domain Layer (optional):** Use Cases encapsulate reusable/complex business logic between UI and Data layers. Named `[Verb][Noun]UseCase` with `operator fun invoke()`. Must be main-safe. No own lifecycle — scoped to consumer.

**Data Layer:** Repositories as single source of truth per data type. Named `[Type]Repository`. Data Sources named `[Type][Source]DataSource`. Repositories expose domain models, not raw API/DB responses. Handle caching, retry, conflict resolution. Never access data sources directly from UI.

**Data flow is unidirectional:** Data flows up (DataSource → Repository → UseCase → ViewModel → UI). Events flow down (UI → ViewModel → UseCase → Repository). All exposed data is immutable.

## Complexity Patterns for Task Decomposition

### UI Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Stateless Compose screen (displays ViewModel state) | Haiku | Mechanical composition, fully specified |
| Compose screen with user interaction (forms, gestures) | Haiku | Clear event/state contract |
| Adaptive layout (window size classes, navigation suite) | Haiku-Sonnet | Platform branching, responsive design |
| Custom Compose layout / Modifier chain | Sonnet | Layout protocol knowledge |
| Complex animation (shared element, motion layout) | Sonnet | Timing, state coordination |
| Compose + View interop (legacy migration) | Sonnet | Two-system coordination |

### ViewModel & State Patterns
| Pattern | Model | Rationale |
|---|---|---|
| ViewModel exposing single StateFlow | Haiku | Standard pattern, clear contract |
| ViewModel with multiple repository dependencies | Haiku-Sonnet | Flow combining, error coordination |
| Sealed UI state with Loading/Success/Error | Haiku | Mechanical pattern, exhaustive when |
| Complex state machine (multi-step flow) | Sonnet | State transitions, edge cases |
| SavedStateHandle integration for process death | Haiku-Sonnet | Serialization strategy |

### Data Layer Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Repository wrapping single data source | Haiku | Mechanical: fetch/cache/return |
| Repository with offline-first strategy | Sonnet | Cache invalidation, sync conflicts |
| Room entity + DAO (single table) | Haiku | Schema is mechanical |
| Room migration / multi-table relationships | Sonnet | Migration strategy, query design |
| DataStore setup (Preferences or Proto) | Haiku | Config-driven, follows pattern |
| Network layer setup (Retrofit + OkHttp) | Haiku-Sonnet | Interceptors, error mapping |

### Platform & Integration Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Hilt module + bindings for a feature | Haiku | Annotation-driven, follows patterns |
| Hilt multi-module DI architecture | Sonnet | Scoping, component hierarchy |
| Navigation graph (Compose Navigation) | Haiku-Sonnet | Route design, deep links, guards |
| Runtime permissions flow | Haiku-Sonnet | UX design, denial handling |
| WorkManager task (one-shot or periodic) | Haiku-Sonnet | Constraints, retry, chaining |
| Platform channel (Flutter ↔ Android) | Sonnet | Cross-boundary contract |
| Foreground service / notification channels | Sonnet | Lifecycle, system interaction |
| Content provider (shared data) | Sonnet | Security, URI design |
| Baseline profile generation | Haiku-Sonnet | Setup is Haiku, critical paths are Sonnet |

### Build & Config Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Build variant / product flavor setup | Sonnet | Build system design decisions |
| Version catalog (libs.versions.toml) | Haiku | Mechanical file editing |
| ProGuard/R8 keep rules | Sonnet | Reflection analysis, library interaction |
| Convention plugin | Sonnet | Build system abstraction |

### Testing Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Unit test for ViewModel/Repository/UseCase | Haiku | Method-level, clear inputs/outputs |
| Compose UI test (single composable) | Haiku | Semantics-based assertions |
| Robolectric test for Android framework code | Haiku-Sonnet | Framework simulation |
| Espresso / instrumented test | Sonnet | Device interaction, async waits |
| End-to-end flow test | Sonnet | Multi-screen, real navigation |

## Decomposition Notes

- **Composables/Screens are Haiku boundaries.** Each screen is self-contained when its ViewModel interface is defined.
- **ViewModels are Haiku boundaries** when repository interfaces exist. ViewModel design (which repos, which flows to combine) is Sonnet.
- **Use Cases are Haiku** when the business rule is specified. Deciding whether to introduce a Use Case is Sonnet.
- **Room entities + DAOs are Haiku** for single-table CRUD. Multi-table joins and migration strategy are Sonnet.
- **Hilt modules are Haiku** when bindings are specified. DI architecture design is Sonnet.
- **Architecture decisions are Sonnet:** Offline-first strategy, state management approach, navigation architecture, DI scoping.
- **Generated code is not a task.** Never create tasks for Hilt-generated components, Room schema JSON, or Dagger files.
- **Prefer feature-first project structure:** `feature/[name]/ui/`, `feature/[name]/data/`, `feature/[name]/domain/`.
