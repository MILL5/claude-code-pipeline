# Android / Kotlin — Test Overlay

<!-- Injected into test-architect-agent at ADAPTER:TECH_STACK_CONTEXT marker -->

## Test Framework: JUnit 4 + Android Testing Libraries

Android tests live in two source sets. Test the architecture layers bottom-up: DataSources → Repositories → UseCases → ViewModels → UI.

- **Local tests** (`src/test/`): Run on JVM without device. Fast. Use for unit tests, ViewModel tests, Robolectric.
- **Instrumented tests** (`src/androidTest/`): Run on device/emulator. Use for UI tests (Espresso, Compose), integration tests.

## Test Structure

```
app/src/
  test/java/com/example/app/
    feature/
      data/
        FeatureRepositoryTest.kt
        FeatureDataSourceTest.kt
      domain/
        FeatureUseCaseTest.kt
      ui/
        FeatureViewModelTest.kt
  androidTest/java/com/example/app/
    feature/
      ui/
        FeatureScreenTest.kt
    e2e/
      CriticalFlowTest.kt
```

Naming: `fun \`description of behavior under test\`()` (backtick style) or `fun featureName_scenario_expectedResult()`.

## Unit Tests (Local — JVM)

Test ViewModels, Repositories, UseCases, and utility functions.

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class FeatureViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: FeatureViewModel
    private val fakeRepository = FakeFeatureRepository()

    @Before
    fun setup() {
        viewModel = FeatureViewModel(
            repository = fakeRepository,
            ioDispatcher = UnconfinedTestDispatcher(),
        )
    }

    @Test
    fun `loadData updates state to Success`() = runTest {
        fakeRepository.emit(listOf(testItem))

        viewModel.loadData()

        assertThat(viewModel.uiState.value).isInstanceOf(UiState.Success::class.java)
        val state = viewModel.uiState.value as UiState.Success
        assertThat(state.items).hasSize(1)
    }

    @Test
    fun `loadData updates state to Error on failure`() = runTest {
        fakeRepository.shouldFail = true

        viewModel.loadData()

        assertThat(viewModel.uiState.value).isInstanceOf(UiState.Error::class.java)
    }
}
```

### MainDispatcherRule

Required for testing ViewModels that use `viewModelScope`:

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    private val testDispatcher: TestDispatcher = UnconfinedTestDispatcher(),
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(testDispatcher)
    }
    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
```

### Mocking Strategy

- **Fakes preferred over mocks** — manual implementations of interfaces that focus on behavior, not call verification.
- **MockK** for Kotlin-first mocking when fakes would be verbose: `mockk<T>()`, `every { }`, `coEvery { }`, `verify { }`, `coVerify { }`.
- **Mockito-Kotlin** as alternative: `mock<T>()`, `whenever().thenReturn()`, `verify()`.
- Mock at boundaries: fake DataSources when testing Repositories, fake Repositories when testing ViewModels.
- Never mock the class under test.

### Flow Testing with Turbine

```kotlin
@Test
fun `state emits Loading then Success`() = runTest {
    viewModel.uiState.test {
        assertThat(awaitItem()).isEqualTo(UiState.Loading)

        viewModel.loadData()

        assertThat(awaitItem()).isInstanceOf(UiState.Success::class.java)
        cancelAndIgnoreRemainingEvents()
    }
}
```

Turbine handles timing, cancellation, and high-frequency emissions. Use `awaitItem()`, `awaitError()`, `awaitComplete()`, `cancelAndIgnoreRemainingEvents()`.

### Coroutine Testing

- `runTest { }` for all coroutine tests — auto-advances virtual time.
- `StandardTestDispatcher()` for tests needing explicit time control (`advanceUntilIdle()`, `advanceTimeBy()`).
- `UnconfinedTestDispatcher()` for tests where execution order doesn't matter.
- Inject test dispatchers via constructor — never rely on `Dispatchers.Main` being the real main dispatcher.
- All test dispatchers in a test should share the same `TestCoroutineScheduler`.

### Room Testing

```kotlin
@RunWith(AndroidJUnit4::class)
class FeatureDaoTest {
    private lateinit var db: AppDatabase

    @Before
    fun setup() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            AppDatabase::class.java,
        ).allowMainThreadQueries().build()
    }

    @After
    fun teardown() {
        db.close()
    }

    @Test
    fun `insert and retrieve feature`() = runTest {
        val entity = FeatureEntity(id = "1", name = "Test")
        db.featureDao().insert(entity)

        val result = db.featureDao().getById("1")
        assertThat(result).isEqualTo(entity)
    }
}
```

## Compose UI Tests

Use `ComposeTestRule` for testing individual composables.

```kotlin
class FeatureScreenTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun `displays loading indicator when loading`() {
        composeTestRule.setContent {
            FeatureScreen(uiState = UiState.Loading)
        }

        composeTestRule
            .onNodeWithTag("loading_indicator")
            .assertIsDisplayed()
    }

    @Test
    fun `clicking item triggers callback`() {
        var clickedId: String? = null

        composeTestRule.setContent {
            FeatureScreen(
                uiState = UiState.Success(items = listOf(testItem)),
                onItemClick = { clickedId = it },
            )
        }

        composeTestRule
            .onNodeWithText(testItem.name)
            .performClick()

        assertThat(clickedId).isEqualTo(testItem.id)
    }
}
```

### Key Compose Test APIs

- `onNodeWithText("text")` — Find by displayed text.
- `onNodeWithTag("tag")` — Find by test tag (`Modifier.testTag("tag")`).
- `onNodeWithContentDescription("desc")` — Find by accessibility description.
- `performClick()`, `performTextInput("text")`, `performScrollTo()` — User actions.
- `assertIsDisplayed()`, `assertTextEquals("text")`, `assertDoesNotExist()` — Assertions.
- `waitForIdle()` — Wait for pending recompositions.
- `createAndroidComposeRule<Activity>()` — When Activity context is needed.

## Espresso (View-based UI Tests)

For legacy View-based UI or hybrid Compose+View screens.

```kotlin
@Test
fun `clicking button shows message`() {
    onView(withId(R.id.button)).perform(click())
    onView(withText("Hello")).check(matches(isDisplayed()))
}
```

## Assertions

- **Truth** (Google): `assertThat(actual).isEqualTo(expected)`, `.isInstanceOf()`, `.hasSize()`, `.contains()`, `.isEmpty()`.
- Preferred over JUnit `assertEquals` for readability and better failure messages.

## Coverage

Gradle task: `./gradlew testDebugUnitTest jacocoTestReport` (requires JaCoCo plugin configuration).

### Coverage Exclusions

Exclude from coverage calculations:
- Hilt-generated: `*_Hilt*`, `*_Factory*`, `*_MembersInjector*`, `Hilt_*`
- Dagger-generated: `*_Provide*Factory*`, `Dagger*Component*`
- Room-generated: `*_Impl*`
- Data binding: `*Binding*`, `*BindingImpl*`
- Build config: `BuildConfig`, `*_BuildConfig*`
- R class: `R.class`, `R$*.class`
- Android framework: `*Activity*`, `*Fragment*` (test ViewModels instead)

## Anti-Patterns

- **Testing implementation details:** Don't verify internal state or call counts — test observable behavior (emitted state, returned values, rendered UI).
- **Shared mutable state between tests:** Each test sets up its own fakes. Use `@Before` for shared setup.
- **Hardcoded delays:** Never use `Thread.sleep()` or `delay()` in tests. Use `runTest` with `advanceUntilIdle()`, Turbine's `awaitItem()`, Compose's `waitForIdle()`.
- **Testing framework code:** Don't test that Hilt injects correctly or Room compiles — test your business logic.
- **Testing generated code:** Don't test Hilt components, Room DAOs' generated SQL, or data class `copy()`/`equals()`.
- **Missing MainDispatcherRule:** ViewModel tests will fail or behave unexpectedly without replacing `Dispatchers.Main`.
- **Collecting StateFlow without Turbine:** Manual collection is racy and flaky. Use Turbine or assert on `.value` directly.
- **Over-mocking:** Prefer fakes for repositories and data sources. Mocks are for verifying interactions with external systems.
