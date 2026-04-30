# Adopting the Swift / iOS Adapter

This adapter activates for Apple-ecosystem projects: iOS, watchOS, macOS, tvOS, and Swift Packages. The pipeline uses Xcode for build and XCTest for tests, with `xccov` for coverage.

## Detection

`init.sh` activates this adapter when any of these exist at the project root:

- `*.xcodeproj` directory
- `*.xcworkspace` directory
- `Package.swift`

## Tools you'll need

| Tool | Why | Notes |
|---|---|---|
| Xcode 15+ | Build + test toolchain | Install via App Store; accept the EULA after install |
| `xcrun` | Sub-tool resolution | Provided by Xcode |
| iOS / watchOS simulators | Test runtime | Install via Xcode > Settings > Platforms |
| `gh` CLI | PR creation by the pipeline | `gh auth status` must exit 0 |

For watchOS apps, the watch-side build/test scheme needs both iPhone + Watch destinations. The adapter's `scripts/build.py` figures this out from your scheme list, but you'll get clearer errors if the scheme is configured properly.

## Bootstrap

```bash
cd your-ios-project
git submodule add https://github.com/MILL5/claude-code-pipeline.git .claude/pipeline
bash .claude/pipeline/init.sh .
```

Expected output:

```
Detected stacks: swift-ios
Symlinks created:
  .claude/agents -> .claude/pipeline/agents
  .claude/skills/* -> .claude/pipeline/skills/*
  .claude/scripts/swift-ios -> .claude/pipeline/adapters/swift-ios/scripts
Wrote .claude/pipeline.config (stacks=swift-ios)
Merged hooks into .claude/settings.json
Generated .claude/CLAUDE.md and .claude/ORCHESTRATOR.md (edit these next)
Generated .claude/local/ overlay templates
```

After bootstrap, edit `.claude/ORCHESTRATOR.md` to capture your scheme names, build targets (e.g., iOS app + Watch app + widgets), and any Apple-specific architecture notes (MVVM, observation, persistence layer).

## Project layout assumed

The adapter has no enforced directory layout — it relies on the `**/*.swift` fallback glob. Both flat (everything in `Sources/`) and target-segregated (multi-target Xcode project) layouts work.

If you have multiple platforms in one repo (e.g., iOS app + watchOS app), the pipeline launches separate build/test invocations per scheme based on what your project declares.

## Build & test commands

```bash
python3 .claude/scripts/swift-ios/build.py
python3 .claude/scripts/swift-ios/test.py
```

`build.py` shells out to `xcodebuild` per active scheme and emits the pipeline's contract line (`BUILD SUCCEEDED | N warning(s)` / `BUILD FAILED | ...`). `test.py` runs `xcodebuild test` with code coverage enabled, parses `.xcresult`, and emits `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%`.

Raw `xcodebuild build`, `xcodebuild test`, `swift build`, and `swift test` invocations are blocked by `hooks.json`. Use the skills.

## First `/orchestrate` run

Inside Claude Code:

```
/orchestrate
```

Then describe a small UI change: *"Add a settings toggle to enable haptic feedback on the timer screen"*. The pipeline will:

1. Ask 1-2 feature-clarifying questions (UI placement, persistence, default state)
2. Generate a Haiku-tier plan (likely 2-3 tasks: model + view + settings persistence)
3. Open a draft PR
4. Run pre-flight build (catches existing scheme/destination issues)
5. Implement, review (with Swift reviewer overlay watching for retain cycles, force-unwraps, MainActor violations), commit
6. Run XCTest with coverage
7. Ask you to manually test on a simulator or device
8. File a token-analysis report

For a small UI feature, expect ~$0.15-0.40 and 8-15 minutes wall-clock (Xcode builds dominate wall-clock cost).

## Common pitfalls

### Simulator availability

`xcodebuild test` needs a destination. If no simulator is installed for the deployment target, tests fail with cryptic errors. Pre-install simulators for your deployment targets in Xcode > Settings > Platforms before running the pipeline.

### Multi-scheme repos (iOS + Watch + Widgets)

Each scheme has its own destination. The default `scripts/test.py` runs all schemes. If you only want to run the iOS app's scheme, pass `--scheme=YourApp` through the test-runner skill — but the implementer agent will run all schemes by default to enforce the regression guard across targets.

### `[weak self]` patterns Haiku may miss

The Swift implementer overlay enforces `[weak self]` in escaping closures. Haiku occasionally cargo-cults `[weak self]` even when not needed (e.g., inside a `Task { @MainActor in ... }` whose lifecycle is already bounded). The reviewer typically catches over-application. If you see false-positive `[weak self]` in implementations, file a docs issue — the implementer overlay may need a refinement.

### Force-unwraps in test code

The Swift reviewer overlay flags force-unwraps in production code as `[should-fix]` or `FAIL`. Tests are exempted by convention (using `try!` or `XCTUnwrap` is fine in tests). The reviewer knows the difference, but it's worth noting if a Haiku implementer over-applies the rule.

### Multi-stack: Flutter app with native Swift modules

If you're embedding native Swift code in a Flutter app, bootstrap both adapters:

```bash
bash .claude/pipeline/init.sh . --stack=flutter --stack=swift-ios
```

The orchestrator routes Dart tasks to Flutter overlays and Swift tasks to Swift overlays. Cross-stack work (e.g., Dart calling into a Swift platform channel) gets the architect's union view of both.

## Where to file issues

Pipeline behavior issues: https://github.com/MILL5/claude-code-pipeline/issues

Adoption pain specific to this stack: same repo, label `type: docs` with `swift-ios` in the title.
