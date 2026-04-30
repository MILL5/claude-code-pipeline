# Adopting the Flutter / Dart Adapter

This adapter activates for Flutter apps and pure-Dart packages. The pipeline runs `flutter analyze` + `dart format` for build, and `flutter test` (unit, widget, golden, integration) for tests. Coverage flows through `lcov`.

## Detection

`init.sh` activates this adapter when:

- `pubspec.yaml` exists and contains the string `flutter:` (i.e., it's a Flutter app, not a pure-Dart package)

Pure-Dart packages without `flutter:` in the manifest aren't auto-detected. Pass `--stack=flutter` explicitly if you want Dart conventions (the overlays still apply).

## Tools you'll need

| Tool | Why | Notes |
|---|---|---|
| Flutter SDK 3.16+ | Build + test toolchain | Or use FVM (Flutter Version Management) |
| Dart SDK | Bundled with Flutter | Don't install separately |
| `lcov` | Coverage post-processing | `brew install lcov` on macOS |
| `gh` CLI | PR creation by the pipeline | `gh auth status` must exit 0 |

If you target iOS or Android natively, also install those platforms' tooling — but for adoption, you can start with Flutter-only and add native adapters later.

## Bootstrap

```bash
cd your-flutter-project
git submodule add https://github.com/MILL5/claude-code-pipeline.git .claude/pipeline
bash .claude/pipeline/init.sh .
```

Expected output:

```
Detected stacks: flutter
Symlinks created:
  .claude/agents -> .claude/pipeline/agents
  .claude/skills/* -> .claude/pipeline/skills/*
  .claude/scripts/flutter -> .claude/pipeline/adapters/flutter/scripts
Wrote .claude/pipeline.config (stacks=flutter)
Merged hooks into .claude/settings.json
Generated .claude/CLAUDE.md and .claude/ORCHESTRATOR.md (edit these next)
Generated .claude/local/ overlay templates
```

For Flutter apps with native code (Swift in `ios/`, Kotlin in `android/`), bootstrap with all three adapters:

```bash
bash .claude/pipeline/init.sh . --stack=flutter --stack=swift-ios --stack=android
```

The orchestrator routes Dart files to Flutter overlays, Swift files to swift-ios overlays, and Kotlin files to Android overlays based on `stack_paths`.

## Project layout assumed

Default `stack_paths` for Flutter:

- `lib/`, `test/`, `integration_test/`

Plus fallback globs for `**/*.dart`, `pubspec.yaml`, `analysis_options.yaml`, `l10n.yaml`, and ARB files in `lib/l10n/`.

This matches the standard `flutter create` layout. If you've reorganized into a multi-package monorepo (e.g., `packages/<name>/lib/`), update `stack_paths.flutter` in `pipeline.config` accordingly.

## Build & test commands

```bash
python3 .claude/scripts/flutter/build.py
python3 .claude/scripts/flutter/test.py
```

`build.py` runs `flutter analyze` + `dart format --set-exit-if-changed` and emits the pipeline's contract line. `test.py` runs `flutter test --machine --coverage`, parses the streaming JSON, post-processes `coverage/lcov.info`, and emits `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%`.

Raw `flutter test`, `flutter build`, and `flutter analyze` are blocked by `hooks.json`.

## First `/orchestrate` run

Inside Claude Code:

```
/orchestrate
```

Then describe a small change: *"Add a pull-to-refresh on the feed screen"*. The pipeline will:

1. Ask 1-2 feature-clarifying questions (where the refresh state lives, error handling)
2. Generate a Haiku-tier plan (likely 1-2 widget tasks)
3. Open a draft PR
4. Run pre-flight build (`flutter analyze`)
5. Implement, review (with Flutter reviewer overlay watching for widget rebuilds, lifecycle, l10n, accessibility)
6. Run unit + widget tests
7. Ask you to manually test
8. File a token-analysis report

For a small widget addition, expect ~$0.10-0.30 and 5-10 minutes wall-clock.

## Common pitfalls

### `const` constructors

The Flutter implementer overlay encourages `const` constructors where eligible. Haiku tends to apply this aggressively, sometimes adding `const` where a parameter prevents it. The reviewer catches mismatches. If you see `const` removed during fix cycles, that's why.

### Golden test snapshot drift

Golden tests (`testWidgets` with `matchesGoldenFile`) are sensitive to renderer / font / OS version. If your CI environment differs from your local environment, golden tests fail intermittently. The pipeline doesn't auto-update goldens — it surfaces failures and asks you to triage. To regenerate locally, run `flutter test --update-goldens` and commit the deltas explicitly.

### `flutter pub get` not in pre-flight

The pipeline's pre-flight build runs `flutter analyze` but does NOT run `flutter pub get` first. If your `pubspec.lock` is out of date or you've just pulled new deps, run `flutter pub get` manually before `/orchestrate`. (This will be folded into pre-flight in a future iteration.)

### Multi-platform: native code review

When you bootstrap with `--stack=flutter --stack=swift-ios --stack=android`, native code edits go through the corresponding native adapter's reviewer (e.g., Swift edits get the swift-ios reviewer overlay's retain-cycle and force-unwrap rules). The Flutter reviewer doesn't second-guess native code.

### State management library not assumed

The Flutter implementer overlay is opinion-light on state management — it doesn't pre-assume Riverpod, Bloc, Provider, or vanilla setState. Whatever your project uses, document the convention in `.claude/local/coding-standards.md` so the implementer follows it.

## Where to file issues

Pipeline behavior issues: https://github.com/MILL5/claude-code-pipeline/issues

Adoption pain specific to this stack: same repo, label `type: docs` with `flutter` in the title.
