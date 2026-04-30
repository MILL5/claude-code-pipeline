# Adopting the React / TypeScript Adapter

This adapter activates when the pipeline detects React in your `package.json`. It covers React + TypeScript projects using Jest or Vitest for tests.

## Detection

`init.sh` activates this adapter when:

- `package.json` exists and contains the string `"react"` (in any dependency field)

If `package.json` exists but no other adapter matched, this adapter activates as a fallback (covers plain TypeScript/JavaScript projects).

## Tools you'll need

| Tool | Why | Notes |
|---|---|---|
| Node.js 18+ | Runtime for npm/yarn/pnpm/bun | Use whatever your `package.json` engines field requires |
| `npm` / `yarn` / `pnpm` / `bun` | Package manager | Detected from your lockfile |
| `tsc` | Type checking during build | Provided by `typescript` devDep |
| Jest or Vitest | Test runner | Detected from `package.json` test script |
| `gh` CLI | PR creation by the pipeline | `gh auth status` must exit 0 |

## Bootstrap

```bash
cd your-react-project
git submodule add https://github.com/MILL5/claude-code-pipeline.git .claude/pipeline
bash .claude/pipeline/init.sh .
```

Expected output:

```
Detected stacks: react
Symlinks created:
  .claude/agents -> .claude/pipeline/agents
  .claude/skills/* -> .claude/pipeline/skills/*
  .claude/scripts/react -> .claude/pipeline/adapters/react/scripts
Wrote .claude/pipeline.config (stacks=react)
Merged hooks into .claude/settings.json
Generated .claude/CLAUDE.md and .claude/ORCHESTRATOR.md (edit these next)
Generated .claude/local/ overlay templates
```

After bootstrap, edit `.claude/ORCHESTRATOR.md` to describe your architecture (component layout, state management, data flow). The architect agent reads this on every run.

## Project layout assumed

Default `stack_paths` for React expect code in:

- `src/frontend/`, `frontend/`, `client/`, or `app/`

Plus a fallback to any `**/*.tsx`, `**/*.jsx`, `**/*.ts`, `**/*.js` file.

If your project uses a non-standard path (e.g., `web/` or `apps/<name>/`), edit `.claude/pipeline.config` after bootstrap:

```ini
stack_paths.react=web/**,apps/*/src/**
```

## Build & test commands

The pipeline calls these via the `build-runner` and `test-runner` skills:

```bash
python3 .claude/scripts/react/build.py
python3 .claude/scripts/react/test.py
```

The build runner shells out to `tsc --noEmit` for type checking and your project's build script (auto-detected from `package.json`). The test runner runs Jest/Vitest with coverage and emits the pipeline's `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%` contract line.

Raw `npm test` and `npx jest` are blocked by `hooks.json` to force pipeline usage and avoid coverage drift. Override the block by running through the skill instead.

## First `/orchestrate` run

Inside Claude Code:

```
/orchestrate
```

Then describe a small feature: *"Add a loading spinner to the homepage data fetch"*. The pipeline will:

1. Ask 1-2 feature-clarifying questions
2. Generate a Haiku-tier plan (likely 1-2 tasks for a small change)
3. Open a draft PR
4. Run pre-flight build to catch any pre-existing TS errors before launching tasks
5. Implement, review, commit
6. Ask you to manually test the PR branch
7. File a token-analysis report

For a 1-2 task change, expect ~$0.05–0.20 in API costs and 3-5 minutes wall-clock.

## Common pitfalls

### `cleanup()` cargo-cult in tests

Haiku used to add `import { cleanup } from '@testing-library/react'` and `afterEach(() => cleanup())` because RTL docs from older versions show this pattern. RTL v9+ auto-registers cleanup. The implementer overlay now explicitly forbids manual `cleanup()` (PR #51), so this should not happen in fresh runs. If you see it, the React adapter overlay may need an update — file an issue.

### Pre-existing TS errors block Haiku

If `tsc --noEmit` fails on the unmodified base, Haiku tasks will hit the same errors and fail. The pre-flight build at Step 1.4 catches this and pauses with three options: abort, continue anyway, or inject a Wave 0 fix. Recommend **inject Wave 0 fix** — let the pipeline handle the blocker before scheduling the real work.

### Multi-stack repos with React + Python

If your repo has both a React frontend and a Python backend, bootstrap both adapters:

```bash
bash .claude/pipeline/init.sh . --stack=react --stack=python
```

The orchestrator routes each task to the correct adapter using `stack_paths`. Use explicit `stack_paths` in `pipeline.config` to avoid ambiguity at the boundary (e.g., a config file used by both).

### `package.json` without React still activates this adapter

The React adapter has a fallback rule that triggers for any `package.json` if no other adapter matched. If you're on a plain Node.js (non-React) project and want a different setup, add `--stack=` flags explicitly to override auto-detection.

## Where to file issues

Pipeline behavior issues: https://github.com/MILL5/claude-code-pipeline/issues

Adoption pain specific to this stack: same repo, label `type: docs` with `react` in the title.
