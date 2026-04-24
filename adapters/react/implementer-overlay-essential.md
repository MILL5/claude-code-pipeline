# React/TypeScript Essential Rules

Critical rules for Haiku execution. Violations will fail code review.

- Never run `git commit`/`git push` — orchestrator commits after review
- TypeScript `strict` mode — no `any` types without a justifying comment
- Named exports (except page/route components if framework requires default)
- Function components only — never class components
- Rules of Hooks: only call at top level, only from React functions
- Complete dependency arrays for `useEffect`, `useMemo`, `useCallback` — never suppress lint warnings
- Cleanup side effects in `useEffect` return functions (timers, subscriptions, abort controllers)
- Proper prop typing with `interface` — destructure in function signature
- Stable, unique `key` props in lists — never array index for dynamic lists
- Handle loading, error, and empty states explicitly in data-fetching components
- `const` by default, `let` only for reassignment, never `var`
