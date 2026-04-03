# Android / Kotlin — Implementer Overlay

<!-- Injected into implementer-agent at ADAPTER:TECH_STACK_CONTEXT marker -->

## Architecture (MVVM + Repository)

- UI elements (Compose or Views) display state from ViewModel — minimal logic (formatting, visibility, navigation triggers).
- ViewModel exposes immutable `StateFlow<UiState>` via backing property pattern (`private val _uiState` / `val uiState`). Never expose `MutableStateFlow` or `MutableLiveData`.
- Define UI state as immutable `data class FeatureUiState(...)`. Use sealed classes/interfaces for `Loading`/`Success`/`Error` variants.
- Repositories are the single source of truth per data type. Output domain models, handle caching, retry, conflict resolution.
- Data sources (network, local DB, preferences) hold no business logic. One per external source.
- Constructor injection via Hilt. `@HiltViewModel` + `@Inject constructor` for ViewModels. `@Binds` for interfaces, `@Provides` for third-party objects.
- All suspend functions must be **main-safe** — move heavy work off main thread with `withContext(dispatcher)`.

## Kotlin Style

- `lowerCamelCase` for functions, properties, parameters, local variables. `UpperCamelCase` for classes, interfaces, objects, type aliases. `SCREAMING_SNAKE_CASE` for constants (`const val`, top-level `val` with no custom getter).
- `val` over `var` — immutability by default. Immutable collections (`List`, `Set`, `Map`) over mutable variants.
- Default parameter values over function overloads.
- Expression bodies (`fun foo() = expr`) for simple single-expression functions.
- String templates (`"Hello $name"`) over concatenation.
- Named arguments for functions with multiple same-type or boolean parameters.
- Trailing commas at declaration sites.
- Higher-order functions (`filter`, `map`, `flatMap`) over imperative loops when intent is clearer.
- Scope functions: `apply` for object configuration, `let` for null-safe transforms, `also` for side effects, `run`/`with` for scope reduction.
- Modifier order: visibility → `final`/`open`/`abstract`/`sealed`/`const` → `override` → `lateinit` → `suspend` → `inner` → `data` → `companion`.
- 4-space indentation, no tabs. Annotations on separate lines before declaration.

## Coroutines & Structured Concurrency

- **Inject dispatchers** — never hardcode `Dispatchers.IO`/`Dispatchers.Default`. Accept as constructor parameter for testability.
- `viewModelScope` for ViewModel coroutines. Never expose suspend functions from ViewModel — launch internally.
- `lifecycleScope` + `repeatOnLifecycle(Lifecycle.State.STARTED)` for collecting flows in Activities/Fragments.
- `withContext(ioDispatcher)` for I/O operations. `withContext(defaultDispatcher)` for CPU-bound work.
- `coroutineScope { }` / `supervisorScope { }` for parallel work in data/domain layers.
- Never use `GlobalScope` directly — inject `CoroutineScope` for work that must outlive the caller.
- Never catch `CancellationException` — it breaks structured concurrency. Always rethrow it.
- Call `ensureActive()` in long-running loops for cooperative cancellation.

## Jetpack Compose

- Composables are functions of state — no side effects in composition. Side effects go in `LaunchedEffect`, `DisposableEffect`, `SideEffect`.
- `remember` for composition-scoped state. `rememberSaveable` for state surviving configuration changes and process death.
- Hoist state: stateless composables receive state + event callbacks from parent. Stateful wrappers create state and pass it down.
- `Modifier` is the first optional parameter. Chain modifiers — order matters (padding before/after background changes behavior).
- Use `key` parameter in `LazyColumn`/`LazyRow` items for stable identity.
- Minimize recomposition scope: extract frequently-changing UI into small composables. Use `derivedStateOf` for computed state.
- Material 3 theming: `MaterialTheme.colorScheme`, `MaterialTheme.typography`, `MaterialTheme.shapes`. Dynamic color with `dynamicDarkColorScheme`/`dynamicLightColorScheme` on Android 12+.

## Lifecycle & Configuration Changes

- Activities/Fragments have ephemeral lifecycles — never store persistent data in them.
- ViewModel persists through configuration changes (rotation, resize, fold). Use `SavedStateHandle` for process death survival.
- `rememberSaveable` in Compose for UI state that survives both.
- ViewModel must **never** hold references to Activity, Context, or View — causes memory leaks.
- Use Application context (`@ApplicationContext`) for long-lived objects via Hilt.

## Persistence

- **Room** for structured data: `@Entity`, `@Dao`, `@Database`. Use KSP (not kapt). Singleton database instance. Suspend DAO functions for coroutine support. Migrations for version changes.
- **DataStore** for key-value preferences (replaces SharedPreferences): fully async via Flow + coroutines, handles corruption.
- **EncryptedSharedPreferences** for sensitive key-value data. Android Keystore for cryptographic keys.

## Error Handling

- Sealed `Result` types for operations that can fail. Forces exhaustive handling via `when`.
- Catch specific exception types — never bare `catch (e: Exception)` unless rethrowing unknown exceptions.
- **Never catch `CancellationException`** — always rethrow.
- `requireNotNull()` / `checkNotNull()` for validation with descriptive messages.
- Avoid `!!` (non-null assertion) — indicates a design problem. Use `?.`, `?:`, `let`, `requireNotNull()`.

## Security

- Never hardcode API keys, secrets, or credentials. Use `local.properties` or `secrets-gradle-plugin` for build-time secrets.
- HTTPS for all network connections. Network security config for certificate pinning.
- `android:exported=false` on all components not shared externally (required API 31+).
- Parameterized queries in Room/ContentProvider — never string-concatenate SQL.
- Never log PII or secrets in production. Strip logging in release builds via R8/ProGuard.
- `SecureRandom` for cryptographic operations — never `java.util.Random`.

## Permissions

- Check permissions before each access — never assume previously granted.
- Request only what's needed. Explain why before requesting.
- Handle denial gracefully — degrade functionality, don't crash.
- `ActivityResultContracts.RequestPermission()` for modern permission requests.

## Build Configuration

- Kotlin DSL (`.gradle.kts`) preferred for new projects.
- Version catalog (`gradle/libs.versions.toml`) as single source of truth for dependency versions.
- Enable `isMinifyEnabled = true` and `isShrinkResources = true` for release builds.
- `compileSdk` = latest stable API. `targetSdk` = latest attested. `minSdk` = business requirement.

## Resources

- No hardcoded strings — use `strings.xml` for all user-facing text (enables localization).
- No hardcoded dimensions — use `dimens.xml`.
- No hardcoded colors — use Material theme tokens.
- Qualifier directories for configuration-specific resources (night, landscape, locale).
