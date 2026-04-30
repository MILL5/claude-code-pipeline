# Adopting the Android / Kotlin Adapter

This adapter activates for native Android projects (Gradle-based, Kotlin or Java sources). The pipeline runs Gradle with the AGP build tool + Android lint for build, and JUnit 4 (Robolectric / Espresso / Compose Testing) for tests with JaCoCo for coverage.

## Detection

`init.sh` activates this adapter when any of these exist at the project root:

- `build.gradle.kts`
- `build.gradle`
- `app/build.gradle.kts`
- `app/build.gradle`

## Tools you'll need

| Tool | Why | Notes |
|---|---|---|
| Android SDK | Build target platforms | Install via Android Studio or sdkmanager |
| Gradle wrapper (`gradlew`) | Bundled with project | Don't install Gradle globally |
| JDK 11+ | Required for AGP 8+ | JDK 17 recommended |
| `gh` CLI | PR creation by the pipeline | `gh auth status` must exit 0 |

The Gradle wrapper handles AGP, Kotlin, and JaCoCo plugin versions. No extra installs needed beyond the wrapper.

## Bootstrap

```bash
cd your-android-project
git submodule add https://github.com/MILL5/claude-code-pipeline.git .claude/pipeline
bash .claude/pipeline/init.sh .
```

Expected output:

```
Detected stacks: android
Symlinks created:
  .claude/agents -> .claude/pipeline/agents
  .claude/skills/* -> .claude/pipeline/skills/*
  .claude/scripts/android -> .claude/pipeline/adapters/android/scripts
Wrote .claude/pipeline.config (stacks=android)
Merged hooks into .claude/settings.json
Generated .claude/CLAUDE.md and .claude/ORCHESTRATOR.md (edit these next)
Generated .claude/local/ overlay templates
```

## Project layout assumed

Default `stack_paths`:

- `app/src/main/`, `app/src/test/`, `app/src/androidTest/`, `android/`

Plus fallback globs for `**/*.kt`, `**/*.java`, `**/build.gradle.kts`, `**/build.gradle`, `**/AndroidManifest.xml`, and `gradle/libs.versions.toml`.

This matches the standard single-module Android Studio layout. For multi-module projects (`feature/`, `core/`, `data/` modules), add patterns to `pipeline.config`:

```ini
stack_paths.android=feature/*/src/**,core/*/src/**,data/*/src/**,app/src/**
```

## Build & test commands

```bash
python3 .claude/scripts/android/build.py
python3 .claude/scripts/android/test.py
```

`build.py` runs `./gradlew assembleDebug lint` and emits the pipeline's contract line (`BUILD SUCCEEDED | N warning(s)` / `BUILD FAILED | ...`). `test.py` runs `./gradlew testDebugUnitTest jacocoTestReport`, parses JUnit XML output and JaCoCo XML reports, and emits `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%`.

Raw `./gradlew test`, `./gradlew assemble`, and `./gradlew lint` are blocked by `hooks.json`.

## First `/orchestrate` run

Inside Claude Code:

```
/orchestrate
```

Then describe a small change: *"Add a 'Dark mode' preference to the settings screen and persist via DataStore"*. The pipeline will:

1. Ask 1-2 feature-clarifying questions (default state, system-following behavior)
2. Generate a Haiku-tier plan (likely 2-3 tasks: composable + ViewModel + DataStore key)
3. Open a draft PR
4. Run pre-flight build (Gradle assemble + lint)
5. Implement, review (with Android reviewer overlay watching for lifecycle, concurrency, security)
6. Run unit tests with JaCoCo coverage
7. Ask you to manually test on emulator or device
8. File a token-analysis report

For a small Compose feature, expect ~$0.20-0.50 and 10-20 minutes wall-clock (Gradle builds dominate).

## Common pitfalls

### Cold-cache Gradle builds

The first `./gradlew assembleDebug` after a clone or `./gradlew clean` downloads the AGP, Kotlin, and dependency JARs. Pre-flight build can take 5-10 minutes from cold. Consider running a manual build once before `/orchestrate` to warm the cache — pre-flight will then complete in seconds.

### `lateinit` on nullable state

The Android implementer overlay forbids `lateinit var` for nullable state (use a nullable type + null check instead). Haiku occasionally misuses `lateinit` on initially-null view bindings. The reviewer catches this; if you see `lateinit` warnings flagged, it's the overlay doing its job.

### Robolectric vs. instrumented tests

The pipeline's `test.py` runs `testDebugUnitTest` only — that's JUnit + Robolectric. It does NOT run `connectedDebugAndroidTest` (instrumented tests on a device/emulator) because that requires a running emulator and significantly longer wall-clock. If your project relies on instrumented tests for coverage, either move logic into Robolectric-friendly tests or invoke the instrumented suite manually outside the pipeline.

### `!!` non-null assertion

Kotlin's `!!` operator is forbidden in production code per the Android implementer overlay. Use `?.`, `?:`, `requireNotNull()`, or `checkNotNull()`. If your existing codebase has `!!` instances, the reviewer flags them as `[should-fix]` rather than `FAIL` to avoid blocking unrelated work.

### Multi-module: where does a task land?

For multi-module projects, the orchestrator resolves task → stack via `stack_paths`. If a task touches `feature/profile/src/main/...`, the Android adapter handles it. If a task touches `build-logic/src/main/...` (Gradle convention plugins), it still routes to Android. Cross-module refactors get the architect's union view.

### Compose vs. View system

The Android implementer overlay assumes Jetpack Compose first, View system as legacy. If your project is mostly XML/Views, document the preference in `.claude/local/coding-standards.md` to override the default. The reviewer overlay watches for Compose anti-patterns (recomposition, state hoisting) but doesn't block Views-based code.

## Where to file issues

Pipeline behavior issues: https://github.com/MILL5/claude-code-pipeline/issues

Adoption pain specific to this stack: same repo, label `type: docs` with `android` in the title.
