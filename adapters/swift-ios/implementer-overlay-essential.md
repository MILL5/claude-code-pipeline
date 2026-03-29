# Swift/iOS Essential Rules

Critical rules for Haiku execution. Violations will fail code review.

- Use Swift's type system: enums for states, Result for errors, optionals only when truly optional
- Handle error cases the brief specifies, using the exact error types provided
- `@MainActor` for UI-related code (ViewModels, UI state management)
- Prefer value types (struct/enum) unless the brief specifies a class
- `guard` for early exits, `if let` / `guard let` for optional binding
- Never force unwrap (`!`) without a comment justifying safety
- Dependency injection via initializers, not singletons
- Prefer `async/await` over completion handlers
- Follow Swift API Design Guidelines: camelCase properties, PascalCase types
