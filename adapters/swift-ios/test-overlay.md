# Swift/iOS Test Patterns

## XCTest Framework Patterns

Write comprehensive XCTest suites following these conventions:

### Test Structure
- Test class inherits from `XCTestCase`
- Test methods named: `test_featureName_scenario_expectedOutcome()`
- Use `setUp()` / `setUpWithError()` for common initialization
- Use `tearDown()` for cleanup and service reset
- Group related tests with `// MARK: - Category Name`

### Common XCTest Patterns
- Use `nonisolated(unsafe)` for test properties when dealing with actor isolation
- Skip permission-requiring tests with `throw XCTSkip("reason")` and add `throws` to function signature
- Test TimeInterval equality with accuracy: `XCTAssertEqual(value, expected, accuracy: 0.001)`
- Use `XCTAssertThrowsError` for testing throwing functions
- Use `XCTestExpectation` with `wait(for:timeout:)` for async operations
- Use meaningful assertion messages: `XCTAssertEqual(actual, expected, "Timer should reset to initial duration")`

### Async Testing
- Use `async` test methods for testing async code: `func test_asyncOperation() async throws`
- For Combine publishers, use `XCTestExpectation` or async stream collection
- Set reasonable timeouts (default 5 seconds, longer for network-dependent tests)

### Mocking & Isolation
- Use protocol-based mocking for external services
- Real singleton services may need `shared` instance with proper cleanup in tearDown
- Dependency injection via initializers enables clean test isolation
- Use `URLProtocol` subclass for network mocking

### Coverage Considerations
- Exclude SwiftUI View files from coverage (visual, hard to unit test)
- Focus coverage on ViewModels, Services, and Model logic
- Exclusion patterns: `*View.swift`, `*/Views/*`, `*Widget*`

## Apple Framework Testing

- **HealthKit**: Handle authorization states, query failures, background delivery
- **WatchConnectivity**: Test connectivity state changes and message passing
- **Timer precision**: Test with sub-second accuracy where relevant
- **State machines**: Verify all valid state transitions AND reject invalid ones
- **Persistence**: Test save/load cycles, migration scenarios, corrupt data recovery
- **Notifications**: Test scheduling logic, not delivery (delivery requires UI testing)

## Anti-Patterns to Avoid
- Don't test SwiftUI view rendering (use previews for that)
- Don't test Apple framework internals (trust the SDK)
- Don't create flaky tests dependent on timing — use expectations
- Don't share state between tests — each test must be independent
