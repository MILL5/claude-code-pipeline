# Flutter / Dart — Architect Overlay

<!-- Injected into architect-agent at ADAPTER:TECH_STACK_CONTEXT marker -->

## Architecture: MVVM with Repository Pattern (Google-Recommended)

**UI Layer:** Views (StatelessWidget/StatefulWidget displaying state) + ViewModels (ChangeNotifier transforming repository data into UI state, exposing Commands for user interactions). Each View pairs with exactly one ViewModel (1:1).

**Data Layer:** Repositories (single source of truth per data type, owns business logic, caching, retry, outputs domain models) + Services (one per data source — REST, local storage, platform API — holds no state, returns Futures/Streams).

**Optional Domain Layer:** Use-Cases/Interactors when merging data from multiple repositories or encapsulating complex business logic that spans repositories.

**Data flow is unidirectional:** Data flows up (Service → Repository → ViewModel → View). User interactions flow down (View → ViewModel → Repository). ViewModels never access Services directly. No repository-to-repository awareness.

## Complexity Patterns for Task Decomposition

### Widget & UI Patterns
| Pattern | Model | Rationale |
|---|---|---|
| StatelessWidget, single-screen view | Haiku | Mechanical composition, fully specified |
| StatefulWidget with ephemeral state (form, animation) | Haiku | Localized setState, clear scope |
| Adaptive/platform-aware widget (Material + Cupertino) | Haiku-Sonnet | Platform branching logic |
| Custom multi-child layout / RenderObject | Sonnet-Opus | Framework-level rendering knowledge |
| Complex animation choreography (staggered, hero, custom) | Sonnet | Timing, controller lifecycle, composition |

### ViewModel & State Patterns
| Pattern | Model | Rationale |
|---|---|---|
| ViewModel + repository wiring (CRUD) | Haiku | Follows established MVVM, contract clear |
| ViewModel with multiple repository dependencies | Haiku-Sonnet | Data merging, state coordination |
| State management architecture (provider setup, DI tree) | Sonnet | Design decisions on scope and granularity |
| Complex reactive flows (Stream composition, real-time) | Sonnet | Concurrency, backpressure, error propagation |

### Data Layer Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Service wrapping REST API (single endpoint) | Haiku | Mechanical: request/response/error |
| Repository with caching + retry logic | Haiku-Sonnet | Policy decisions, invalidation strategy |
| Local persistence (Hive, sqflite, shared_preferences) | Haiku-Sonnet | Schema design, migration |
| Code generation setup (freezed, json_serializable) | Haiku | Config-driven, follows established patterns |

### Platform & Integration Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Platform channel design (Pigeon/MethodChannel) | Sonnet | Cross-boundary contract, error handling |
| Navigation/routing architecture (go_router) | Sonnet | Deep links, guards, redirect logic |
| Internationalization architecture (ARB, gen-l10n) | Haiku-Sonnet | Setup is mechanical, pluralization rules need judgment |
| App-wide error handling strategy | Sonnet | FlutterError + PlatformDispatcher + Result pattern |
| Multi-isolate computation strategy | Sonnet | Concurrency design, message passing |
| Cross-cutting theming (Material 3, dynamic color) | Haiku-Sonnet | Token application is Haiku, theme architecture is Sonnet |

### Testing Patterns
| Pattern | Model | Rationale |
|---|---|---|
| Unit test for service/repository/ViewModel | Haiku | Method-level, clear inputs/outputs |
| Widget test for single widget | Haiku | pump/find/expect pattern |
| Golden test setup and maintenance | Haiku-Sonnet | Setup is Sonnet, individual goldens are Haiku |
| Integration test for user journey | Sonnet | Multi-screen flow, async, platform interaction |

## Decomposition Notes

- **Widgets are Haiku boundaries.** Each widget is a self-contained unit when its props/state contract is defined.
- **ViewModels are Haiku boundaries** when the repository interface is already defined. If the ViewModel design requires choosing which repositories to depend on, that's Sonnet.
- **Services are Haiku** when the API contract (endpoint, request/response shapes) is specified in the brief.
- **Architecture decisions are Sonnet:** Which state management approach, how to structure the DI tree, navigation guard strategy, error handling philosophy.
- **Platform channel design is Sonnet:** Requires contract design across Dart ↔ native boundary. Implementation of the Dart side is Haiku once the contract exists.
- **Prefer feature-first decomposition** — group by feature (lib/ui/feature_name/, lib/data/repositories/, lib/data/services/) not by layer.
- **Generated code is not a task.** Never create tasks for `*.g.dart` or `*.freezed.dart` files — these are produced by `build_runner`.
