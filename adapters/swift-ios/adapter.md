# Swift/iOS Adapter

## Stack Metadata

- **Stack name:** `swift-ios`
- **Display name:** Swift / iOS (Xcode)
- **Languages:** Swift
- **Build system:** Xcode (xcodebuild) or Swift Package Manager
- **Test framework:** XCTest
- **Coverage tool:** xccov (via xcresult bundle)

## Build & Test Commands

- **Build:** `python3 .claude/scripts/build.py [--project-dir .] [--scheme <name>]`
- **Test:** `python3 .claude/scripts/test.py [--project-dir .] [--scheme <name>] [--no-coverage] [--exclude-from-coverage '<pattern>']`

## Blocked Commands

These commands are blocked by hooks and must use the pipeline skills instead:
- `xcodebuild build` / `xcodebuild test` -> use `build-runner` / `test-runner` skill
- `swift build` / `swift test` -> use `build-runner` / `test-runner` skill
- `swiftc` -> use `build-runner` skill

## Overlay Files

| Overlay | Agent | Purpose |
|---------|-------|---------|
| `architect-overlay.md` | architect-agent | Apple framework complexity patterns |
| `implementer-overlay.md` | implementer-agent | Swift code quality rules, MVVM conventions |
| `reviewer-overlay.md` | code-reviewer-agent | iOS/watchOS-specific review checklist |
| `test-overlay.md` | test-architect-agent | XCTest patterns and Apple framework testing |

## Project Detection

This adapter activates when the project root contains any of:
- `*.xcodeproj`
- `*.xcworkspace`
- `Package.swift`

## Common Conventions

- **Architecture:** MVVM with protocol-driven services
- **Concurrency:** `@MainActor` for ViewModels and UI code, async/await for services
- **Persistence:** Varies by project (UserDefaults, Core Data, SwiftData, file system)
- **Dependency injection:** Via initializers, not singletons (unless project-specific)
- **Naming:** Swift API Design Guidelines — camelCase properties, PascalCase types
- **Error handling:** Result type or throwing functions, never force unwrap without justification
