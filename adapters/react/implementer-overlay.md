# React/TypeScript Implementer Rules

## Code Quality Rules (Rule 4)

Within the boundaries of what the brief asks for, write clean React/TypeScript:
- Enable TypeScript `strict` mode -- no `any` types without a justifying comment
- Use proper prop typing with `interface` or `type` (prefer `interface` for component props)
- Include JSDoc comments on exported functions, hooks, and complex types
- Use `const` by default, `let` only when reassignment is needed, never `var`
- Prefer named exports over default exports (except for page/route components if framework requires it)
- Use early returns for guard clauses
- Keep components focused -- if a component exceeds ~150 lines, it likely needs extraction

## React Hooks Rules

- Follow the Rules of Hooks: only call hooks at the top level, only call hooks from React functions
- Always specify complete dependency arrays for `useEffect`, `useMemo`, `useCallback`
- Never lie about dependencies -- if ESLint warns about a missing dep, fix the logic, don't suppress
- Use `useCallback` for event handlers passed to memoized children
- Use `useMemo` for expensive computations, not for every variable
- Cleanup side effects in `useEffect` return functions (timers, subscriptions, abort controllers)
- Prefer `useReducer` over multiple related `useState` calls

## Component Patterns

- Prefer function components -- never use class components for new code
- Type props with an interface: `interface ButtonProps { label: string; onClick: () => void; }`
- Use `React.FC` sparingly (it adds implicit `children` in older versions) -- prefer explicit typing
- Destructure props in the function signature: `function Button({ label, onClick }: ButtonProps)`
- Use `children` prop type as `React.ReactNode` when needed
- Colocate related code: component, styles, tests, and types in the same directory
- Use `React.forwardRef` when wrapping native elements or exposing imperative handles

## Styling Conventions

- Follow the project's established styling approach (CSS Modules, Tailwind, styled-components, etc.)
- Avoid inline styles except for truly dynamic values (e.g., computed positions)
- Use CSS custom properties for theming over JS-based theme objects when possible
- Ensure responsive design with appropriate breakpoints

## Error Handling

- Use Error Boundaries for catching render errors in component trees
- Handle loading, error, and empty states explicitly in data-fetching components
- Use `try/catch` in async event handlers and effects
- Never swallow errors silently -- log or display them appropriately
- Type error states properly (`Error | null`, not `any`)

## Performance Basics

- Use `key` prop correctly in lists (stable, unique identifiers, never array index for dynamic lists)
- Avoid creating new objects/arrays in render (move to `useMemo` or outside component)
- Use `React.memo` for components that receive the same props frequently
- Lazy load heavy components with `React.lazy` and `Suspense`
- Avoid unnecessary re-renders by lifting state to the appropriate level

## Testing

When writing tests with `@testing-library/react` (RTL), the library already handles common test-setup mechanics. Manual duplication is dead code that the reviewer will reject:

- Do NOT import or call `cleanup()` in test files — RTL registers it automatically via `afterEach`.
- Do NOT wrap RTL helpers (`render`, `userEvent`, `fireEvent`, `waitFor`, `findBy*`) in `act()` — they already wrap it internally. Manual `act()` is only needed for direct state mutations outside RTL.
- Do NOT use `container.querySelector` to find elements — use RTL queries: `getByRole`, `getByLabelText`, `getByPlaceholderText`, `getByText`, falling back to `getByTestId` only when no accessible query works.

## Project Conventions

Key conventions for React/TypeScript projects (the context brief overrides these if different):
- Component-based architecture with hooks for state management
- Dependency injection via props and context, not module-level singletons
- Prefer composition over inheritance
- Use TypeScript path aliases for clean imports (`@/components`, `@/hooks`)
- Keep business logic in custom hooks, not in components
- Use `async/await` over `.then()` chains
