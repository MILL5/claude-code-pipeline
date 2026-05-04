# Claude Code Instructions

## Session Initialization

Role: You are a senior Python developer.

Context: This is a small Python project used as a pipeline benchmark fixture. It is intentionally minimal so the pipeline's behavior is what's measured, not the surrounding codebase.

Setup: At the start of each session, read `.claude/ORCHESTRATOR.md` for architecture, conventions, and current state.

## Workflow Rules

See agent definitions in `.claude/agents/` for per-role guidance (planning, implementation, review, testing).

## Build & Test (Mandatory Skills)

**PreToolUse hooks enforce these rules — violations are blocked automatically.**

- **Builds:** Use the `build-runner` skill (or `python3 .claude/scripts/python/build.py` for subagents)
- **Tests:** Use the `test-runner` skill (or `python3 .claude/scripts/python/test.py` for subagents)
- **Forbidden:** raw `pytest`, `python -m pytest`, `mypy` — all blocked by hook
- **Also blocked:** `grep`, `cat`, `head`, `tail`, `find`, `sed`, `awk` via Bash — use Grep, Read, Glob, Edit tools instead

When presenting test results: show the Summary line first, then per-target coverage, then failures table (if any). Never invent results.
