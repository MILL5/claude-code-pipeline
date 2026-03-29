# Swift/iOS Architect Context

## Project Context

This is a Swift/iOS project built with Xcode. When planning, account for:
- Multiple targets (iOS app, watchOS app, widgets, extensions) — each may need separate build/test schemes
- Platform-specific APIs that don't cross-compile between iOS and watchOS
- App Group containers for shared data between app and extensions
- The 4-file rule: tasks touching more than 3 files must be split into smaller tasks

## Apple Framework Integration Patterns

When planning tasks that involve Apple frameworks, account for their specific complexity:

- **HealthKit**: Authorization flow is a design decision (Sonnet). Individual workout type recording can be Haiku tasks.
- **WatchConnectivity**: Session lifecycle and activation handling is irreducibly complex (Sonnet). Individual message handlers can be Haiku.
- **ActivityKit / Live Activities**: ActivityAttributes definition is Haiku. Lifecycle management tied to app state is Sonnet.
- **AVAudioSession**: Category configuration and interruption handling is Sonnet (iOS audio session categories interact in non-obvious ways). Individual sound playback is Haiku.
- **BGTaskScheduler**: Registration and scheduling logic is Sonnet. The work performed inside a background task can be Haiku if self-contained.
- **Core Data / SwiftData**: Schema definition is Haiku. Migration logic is Sonnet. Concurrent access patterns are Sonnet/Opus.
- **CloudKit**: Record type definition is Haiku. Sync conflict resolution is Sonnet/Opus.
- **StoreKit 2**: Product definition and entitlement checking is Haiku. Transaction verification and receipt validation is Sonnet.
- **Push Notifications**: Registration is Haiku. Rich notification service extensions with media handling is Sonnet.

These patterns help assign the right model to framework integration tasks without under-estimating.

## Swift-Specific Decomposition Notes

- Protocol definitions and conformances are natural Haiku boundaries — define the protocol (Sonnet if non-trivial), then implement each conformance as a separate Haiku task
- SwiftUI views are typically Haiku tasks when the layout is specified; complex custom layouts or animations may need Sonnet
- Combine/async pipelines that coordinate multiple publishers need Sonnet for the pipeline design, Haiku for individual operators
