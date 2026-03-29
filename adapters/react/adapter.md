# React/TypeScript Adapter

## Stack Metadata

- **Stack name:** `react`
- **Display name:** React / TypeScript
- **Languages:** TypeScript, JavaScript
- **Build system:** npm / yarn / pnpm / bun + tsc / esbuild / webpack / vite
- **Test framework:** Jest or Vitest
- **Coverage tool:** istanbul (Jest default) or v8 (Vitest default)

## Build & Test Commands

- **Build:** `python3 .claude/scripts/build.py [--project-dir .] [--scheme <script-name>] [--configuration dev|production]`
- **Test:** `python3 .claude/scripts/test.py [--project-dir .] [--scheme <script-name>] [--no-coverage] [--exclude-from-coverage '<pattern>']`

## Blocked Commands

These commands are blocked by hooks and must use the pipeline skills instead:
- `npm test` / `npx jest` / `npx vitest` -> use `build-runner` / `test-runner` skill
- `yarn test` / `pnpm test` -> use `build-runner` / `test-runner` skill
- `node --test` -> use `test-runner` skill

## Overlay Files

| Overlay | Agent | Purpose |
|---------|-------|---------|
| `architect-overlay.md` | architect-agent | React component hierarchy and state management patterns |
| `implementer-overlay.md` | implementer-agent | TypeScript strict mode, React hooks rules, component patterns |
| `reviewer-overlay.md` | code-reviewer-agent | React/TypeScript-specific review checklist |
| `test-overlay.md` | test-architect-agent | Jest/Vitest + React Testing Library patterns |

## Project Detection

This adapter activates when the project root contains:
- `package.json` with `react` in `dependencies` or `devDependencies`

## Common Conventions

- **Architecture:** Component-based with hooks for state and side effects
- **State management:** React Context for simple state, Redux/Zustand/Jotai for complex state
- **Styling:** CSS Modules, Tailwind CSS, styled-components, or CSS-in-JS
- **Routing:** React Router or Next.js file-based routing
- **Data fetching:** TanStack Query, SWR, or framework-specific (Next.js Server Components)
- **TypeScript:** Strict mode enabled, no `any` types without justification
- **Naming:** camelCase for variables/functions, PascalCase for components/types, kebab-case for files (or PascalCase for components)
- **Error handling:** Error boundaries for UI, try/catch for async operations, proper error states in UI
