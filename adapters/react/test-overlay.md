# React Test Patterns

## Jest/Vitest + React Testing Library

Write comprehensive test suites following these conventions:

### Test Structure
- Use `describe` blocks to group related tests by component/hook/function
- Use `it` or `test` for individual test cases with descriptive names: `it('renders error message when API call fails', ...)`
- Use `beforeEach` / `afterEach` for setup and cleanup
- Use `beforeAll` / `afterAll` for expensive one-time setup (e.g., mock server)
- Group related tests with nested `describe` blocks for different scenarios

### React Testing Library Patterns
- Query by accessibility role first: `screen.getByRole('button', { name: /submit/i })`
- Fall back to `getByLabelText`, `getByPlaceholderText`, `getByText` in that order
- Use `getByTestId` only as a last resort when no accessible query works
- Use `screen` object instead of destructuring from `render()`
- Use `userEvent` over `fireEvent` for realistic user interactions:
  ```typescript
  const user = userEvent.setup();
  await user.click(screen.getByRole('button'));
  await user.type(screen.getByRole('textbox'), 'hello');
  ```
- Use `waitFor` for assertions on async state changes:
  ```typescript
  await waitFor(() => {
    expect(screen.getByText('Success')).toBeInTheDocument();
  });
  ```
- Use `within` to scope queries to a specific container:
  ```typescript
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText('Confirm')).toBeInTheDocument();
  ```

### Mocking
- Mock modules with `jest.mock('module-name')` or `vi.mock('module-name')`
- Mock fetch/API calls with MSW (Mock Service Worker) for integration tests
- Mock individual functions: `jest.fn()` / `vi.fn()` with `.mockReturnValue()` or `.mockResolvedValue()`
- Reset mocks in `afterEach`: `jest.restoreAllMocks()` / `vi.restoreAllMocks()`
- Mock hooks by mocking the module they come from, not by mocking React internals
- Use `jest.spyOn` / `vi.spyOn` for partial mocks of existing objects

### Async Testing
- Always `await` userEvent interactions
- Use `waitFor` for assertions that depend on async state updates
- Use `findBy*` queries (which combine `getBy*` + `waitFor`) for elements that appear asynchronously
- Use `act()` only when React Testing Library utilities don't already wrap it (rare)
- Set up MSW handlers in `beforeAll`, reset in `afterEach`

### Snapshot Testing
- Use sparingly -- only for components with complex but stable markup
- Prefer inline snapshots for small outputs: `expect(result).toMatchInlineSnapshot()`
- Always review snapshot changes in PR diffs -- never blindly update
- Never snapshot entire page components (too fragile, too large)

### Custom Hook Testing
- Use `renderHook` from `@testing-library/react`:
  ```typescript
  const { result } = renderHook(() => useCounter(0));
  act(() => result.current.increment());
  expect(result.current.count).toBe(1);
  ```
- Wrap hooks that need providers in a `wrapper` option:
  ```typescript
  renderHook(() => useAuth(), { wrapper: AuthProvider });
  ```

### Coverage Considerations
- Exclude configuration files from coverage (vite.config.ts, jest.config.ts, etc.)
- Exclude type-only files (.d.ts)
- Exclude barrel/index files that only re-export
- Focus coverage on components, hooks, and utility functions
- Exclusion patterns: `*.config.*`, `*.d.ts`, `*/types/*`, `**/index.ts` (barrel files)

## Anti-Patterns to Avoid
- Don't test implementation details (internal state, private methods, component internals)
- Don't test third-party library behavior (trust the library)
- Don't use `container.querySelector` -- use RTL queries instead
- Don't test CSS styles directly -- test behavior and accessibility
- Don't create flaky tests dependent on timing -- use `waitFor` and `findBy`
- Don't share mutable state between tests -- each test must be independent
- Don't use `act()` wrapping when RTL already handles it
