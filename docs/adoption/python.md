# Adopting the Python Adapter

This adapter activates when the pipeline detects Python project metadata. It covers libraries, services (Django, FastAPI, Flask), and async/await codebases. The pipeline uses `mypy` + `ruff` for build, `pytest` + `pytest-cov` for tests.

## Detection

`init.sh` activates this adapter when any of these exist at the project root:

- `pyproject.toml`
- `setup.py`
- `setup.cfg`
- `requirements.txt`

## Tools you'll need

| Tool | Why | Notes |
|---|---|---|
| Python 3.9+ | Runtime | Earlier versions may work but type-hints assume 3.9+ |
| `pip` / `poetry` / `uv` | Package manager | Detected from your lockfile |
| `mypy` | Type checking | Used by `build.py` |
| `ruff` | Lint + format | Used by `build.py` |
| `pytest` + `pytest-cov` | Test runner + coverage | Used by `test.py` |
| `gh` CLI | PR creation by the pipeline | `gh auth status` must exit 0 |

Install pipeline-required tools: `pip install mypy ruff pytest pytest-cov`

## Bootstrap

```bash
cd your-python-project
git submodule add https://github.com/MILL5/claude-code-pipeline.git .claude/pipeline
bash .claude/pipeline/init.sh .
```

Expected output:

```
Detected stacks: python
Symlinks created:
  .claude/agents -> .claude/pipeline/agents
  .claude/skills/* -> .claude/pipeline/skills/*
  .claude/scripts/python -> .claude/pipeline/adapters/python/scripts
Wrote .claude/pipeline.config (stacks=python)
Merged hooks into .claude/settings.json
Generated .claude/CLAUDE.md and .claude/ORCHESTRATOR.md (edit these next)
Generated .claude/local/ overlay templates
```

If `pyproject.toml` declares Azure SDK packages (e.g., `azure-identity`, `azure-storage-blob`), `init.sh` also activates the cross-cutting `azure-sdk` overlay automatically.

## Project layout assumed

Default `stack_paths` expect code in:

- `src/backend/`, `backend/`, `server/`, or `api/`

Plus a fallback to any `**/*.py` file.

For src-layout packages (`src/<package_name>/`), this works as-is. For flat-layout packages (`<package_name>/` at root), consider adding the path explicitly to `pipeline.config`:

```ini
stack_paths.python=mypackage/**,tests/**
```

## Build & test commands

```bash
python3 .claude/scripts/python/build.py
python3 .claude/scripts/python/test.py
```

The build runner runs `ruff check` + `mypy` and emits `BUILD SUCCEEDED | N warning(s)` or `BUILD FAILED | ...`. The test runner runs `pytest --cov` and emits the `Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%` contract line.

Raw `pytest`, `mypy`, and `ruff` invocations are blocked by `hooks.json`. Use the skills instead.

## First `/orchestrate` run

Inside Claude Code:

```
/orchestrate
```

Then describe a small change: *"Add a `/healthz` endpoint that returns the current schema version"*. The pipeline will:

1. Ask 1-2 feature-clarifying questions (likely about response shape and authentication)
2. Generate a Haiku-tier plan
3. Open a draft PR
4. Run pre-flight build (`mypy` + `ruff`)
5. Implement, review (with the Python reviewer overlay enforcing GIL, security, resource management), commit
6. Run tests (must hit ≥90% coverage)
7. Ask you to manually test
8. File a token-analysis report

For a small endpoint addition, expect ~$0.10-0.30 and 5-8 minutes wall-clock.

## Common pitfalls

### Mutable default arguments

The Python implementer overlay forbids `def f(items=[])` (a classic Python footgun). Haiku-emitted code uses `None` sentinel + `if items is None: items = []`. If you have legacy code with mutable defaults, the reviewer flags it as a `[should-fix]`.

### Test discovery on flat-layout packages

`pytest` defaults to discovering tests under `tests/` or any `test_*.py` file. If your tests live elsewhere, set `[tool.pytest.ini_options].testpaths` in `pyproject.toml`. The pipeline trusts your project's `pytest` config — it does not pass extra `--rootdir` flags.

### Coverage gate at 90%

The implementer's Rule 7 enforces ≥90% coverage. On a fresh project with low coverage, the first feature run may fail this gate. Two paths:

1. Lower the gate temporarily via the brief's "Verification" override (state explicitly that this run has a coverage exception; the test-architect agent will not generate extra tests beyond the brief)
2. Run the test-architect agent first to bring overall coverage up to 90% before triggering `/orchestrate`

### Async test gotchas

If your project uses `pytest-asyncio`, configure `asyncio_mode = "auto"` in `pyproject.toml` so the implementer doesn't have to mark every test `@pytest.mark.asyncio`. The Python implementer overlay assumes auto mode.

### Multi-stack repos with React + Python

A common shape: React in `frontend/`, Python in `backend/`. Bootstrap both:

```bash
bash .claude/pipeline/init.sh . --stack=react --stack=python
```

Use explicit `stack_paths` in `pipeline.config` to keep the boundary clean. The orchestrator routes each task to the correct adapter; the reviewer agent for a wave loads the union of stacks present in that wave's tasks.

## Where to file issues

Pipeline behavior issues: https://github.com/MILL5/claude-code-pipeline/issues

Adoption pain specific to this stack: same repo, label `type: docs` with `python` in the title.
