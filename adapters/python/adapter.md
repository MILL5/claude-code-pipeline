# Python Adapter

## Stack Metadata

- **Stack name:** `python`
- **Display name:** Python
- **Languages:** Python
- **Build system:** pip / poetry / uv / pdm + mypy / pyright / ruff
- **Test framework:** pytest
- **Coverage tool:** coverage.py / pytest-cov

## Build & Test Commands

- **Build (lint/typecheck):** `python3 .claude/scripts/python/build.py [--project-dir .] [--scheme <tool>] [--configuration <strict|relaxed>]`
- **Test:** `python3 .claude/scripts/python/test.py [--project-dir .] [--scheme <suite>] [--no-coverage] [--exclude-from-coverage '<pattern>']`

## Blocked Commands

These commands are blocked by hooks and must use the pipeline skills instead:
- `pytest` / `python -m pytest` -> use `test-runner` skill
- `mypy` / `python -m mypy` / `pyright` -> use `build-runner` skill
- `ruff` / `ruff check` / `ruff format` -> use `build-runner` skill

## Overlay Files

| Overlay | Agent | Purpose |
|---------|-------|---------|
| `architect-overlay.md` | architect-agent | Python architecture and decomposition patterns |
| `implementer-overlay.md` | implementer-agent | Python code quality rules, PEP conventions |
| `reviewer-overlay.md` | code-reviewer-agent | Python-specific review checklist |
| `test-overlay.md` | test-architect-agent | pytest patterns and testing conventions |

## Project Detection

This adapter activates when the project root contains any of:
- `pyproject.toml`
- `setup.py`
- `setup.cfg`
- `requirements.txt`

## Common Conventions

- **Type hints:** PEP 484 type annotations on all public functions and methods
- **Data containers:** `dataclasses` or `pydantic` models, not raw dicts
- **Concurrency:** `asyncio` with `async/await` for I/O-bound work; `concurrent.futures` for CPU-bound
- **Error handling:** Specific exception types, never bare `except:`
- **Imports:** Organized as stdlib / third-party / local, one group per blank line
- **Strings:** f-strings for interpolation, raw strings for regex
- **Paths:** `pathlib.Path` over `os.path` string manipulation
- **Naming:** snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE for constants
