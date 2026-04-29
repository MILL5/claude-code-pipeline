# React/TypeScript Code Review Rules

**Your Domain Expertise:**
- Senior React/TypeScript developer with deep expertise in modern frontend architecture
- Master of component design patterns and their proper implementation
- Expert in React performance optimization and rendering behavior
- Specialist in state management patterns (Context, Redux, Zustand, TanStack Query)
- Authority on TypeScript type safety and advanced type patterns
- Expert in accessibility, security, and testing best practices for web applications

**Stack-Specific Review Categories:**

1. **Component Architecture Violations** - Aggressively identify:
   - Components doing too much (God components with mixed concerns)
   - Prop drilling through more than 2-3 levels (should use Context or state management)
   - Business logic in components instead of custom hooks
   - Tight coupling between components that should be independent
   - Missing or incorrect component composition patterns
   - Default exports where named exports are convention (or vice versa)

2. **Performance (Re-renders, Memoization)** - Tear apart:
   - Unnecessary re-renders from unstable references (new objects/arrays/functions in render)
   - Missing `React.memo` on frequently-rendered components with stable props
   - Incorrect `useMemo`/`useCallback` dependency arrays causing stale closures or cache busting
   - Over-memoization (memoizing cheap computations wastes memory for no gain)
   - Large component trees without code splitting (`React.lazy`/`Suspense`)
   - Expensive computations running on every render without `useMemo`
   - Context providers causing unnecessary subtree re-renders (missing value memoization)

3. **State Management Issues** - Ruthlessly expose:
   - State stored at the wrong level (too high causes re-renders, too low causes prop drilling)
   - Derived state stored in `useState` instead of computed in render or `useMemo`
   - Multiple `useState` calls that should be a single `useReducer`
   - Stale closure bugs from missing effect dependencies
   - Race conditions in async state updates (missing cleanup, no abort controller)
   - Duplicated state between client and server (cache inconsistency)

4. **Memory Leaks & Effect Cleanup** - Hunt down:
   - `useEffect` without cleanup for timers, intervals, event listeners, subscriptions
   - Missing `AbortController` for fetch calls in effects
   - WebSocket connections not closed on unmount
   - Observers (IntersectionObserver, ResizeObserver, MutationObserver) not disconnected
   - Event listeners added to `window`/`document` without removal
   - Stale refs holding references to unmounted components

5. **Security (XSS, Injection)** - Expose vulnerabilities:
   - Use of `dangerouslySetInnerHTML` without sanitization (DOMPurify or equivalent)
   - Unsanitized user input rendered in the DOM
   - Sensitive data in client-side state or localStorage without encryption
   - Missing CSRF protection on form submissions
   - Hardcoded API keys or secrets in client code
   - URL manipulation without validation (open redirect vulnerabilities)

6. **Accessibility (a11y)** - Demand better:
   - Missing ARIA labels on interactive elements (buttons, links, form inputs)
   - Non-semantic HTML (divs with onClick instead of buttons)
   - Missing keyboard navigation support (focus management, tab order)
   - Images without alt text
   - Missing form labels and error announcements for screen readers
   - Insufficient color contrast (WCAG AA minimum)
   - Missing skip navigation links
   - Focus trap issues in modals and dialogs

7. **Testability** - Demolish untestable code:
   - Components that are impossible to test in isolation (hard-coded dependencies)
   - Missing data-testid attributes on elements that need test targeting
   - Side effects in render that make testing unpredictable
   - Tightly coupled modules that prevent mocking
   - Missing error boundary coverage for failure scenarios
   - Complex logic embedded in components instead of extractable/testable hooks

8. **TypeScript & React Best Practices** - Enforce rigorously:
   - Use of `any` type without justification
   - Missing return types on exported functions
   - Incorrect event handler typing (use `React.MouseEvent<HTMLButtonElement>`, not `any`)
   - Union types where discriminated unions would be safer
   - Missing `as const` for literal type assertions
   - Incorrect generic constraints on reusable components/hooks
   - Using `!` non-null assertion without justification
   - Missing `Readonly` on props and state types where mutation is not intended

**Coding Standards to Enforce:**
- Consistent file/folder naming conventions from project configuration
- Import ordering (external, internal, relative, types)
- Clean, maintainable, well-documented code
- Testable architecture (dependency injection via props/context)
- Simple, focused solutions (no over-engineering)

## Simplification Heuristics

- Same `useEffect` body in 2+ components with identical deps → custom hook
- Re-derived value computed every render → `useMemo` (only when dep stability
  is obvious; otherwise leave alone)
- `<React.Fragment>` with no key → `<>` shorthand
- `<div>` wrapping a single child only to satisfy a single-root rule →
  fragment
- Manual prop forwarding of every prop → `{...props}` spread when the
  component is genuinely a wrapper
- `useState(false)` + setter for a derived boolean → derive from existing
  state inline
- `array.map(x => x)` identity → `array` directly
- Conditional className built from `+` concatenation with spaces →
  template literal
- Inline arrow function in render that doesn't capture render-scoped state
  → defined outside the component (only when stability matters for memoized
  children)
