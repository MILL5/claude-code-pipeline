# Android / Kotlin — Essential Rules (Haiku)

- Never run `git commit`/`git push` — orchestrator commits after review
- MVVM: UI displays ViewModel state via StateFlow, Repositories own data logic
- Backing property: private MutableStateFlow, public StateFlow — never expose mutable
- Sealed classes for UI state (Loading/Success/Error) — exhaustive `when`
- Inject dispatchers — never hardcode. All suspend functions main-safe
- Never catch CancellationException. Catch specific types only
- `val` over `var`, immutable collections, data class for state
- Hilt DI: `@HiltViewModel`, `@Inject constructor`, `@Binds` for interfaces
- ViewModel must never hold Activity/Context/View — memory leak
- No hardcoded strings/colors/dimensions — use resources and theme tokens
- `android:exported=false` on internal components, parameterized SQL
- `remember`/`rememberSaveable` for Compose state, `key` in LazyColumn
- Avoid `!!` — use `?.`, `?:`, `requireNotNull()`
