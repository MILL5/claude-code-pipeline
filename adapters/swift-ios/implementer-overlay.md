# Swift/iOS Implementer Rules

## Code Quality Rules (Rule 4)

Within the boundaries of what the brief asks for, write clean Swift:
- Use `// MARK:` sections for logical grouping
- Include brief doc comments on public API
- Use Swift's type system (enums for states, Result for errors, optionals only when truly optional)
- Handle the error cases the brief specifies, using the exact error types it provides
- Use `@MainActor` when the brief indicates UI-related code (ViewModels, UI state management)
- Prefer value types (struct/enum) unless the brief specifies a class
- Use `guard` for early exits, `if let` / `guard let` for optional binding
- Follow Swift API Design Guidelines for naming (camelCase properties, PascalCase types)

## Project Conventions

Key conventions for Swift/iOS projects (the context brief overrides these if different):
- MVVM architecture with services for business logic
- Dependency injection via initializers, not singletons
- `@MainActor` for ViewModels and UI code
- Protocol-oriented design for testability
- Prefer `async/await` over completion handlers
- Use `Codable` for serialization unless the brief specifies otherwise
- Never force unwrap (`!`) without a comment justifying why it's safe
