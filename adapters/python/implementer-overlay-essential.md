# Python Essential Rules

Critical rules for Haiku execution. Violations will fail code review.

- Never run `git commit`/`git push` — orchestrator commits after review
- Type annotations on all function signatures (parameters and return types)
- Never use `Any` without a comment explaining why
- Catch specific exception types — never bare `except:` or `except Exception:`
- Use `raise ... from e` to preserve exception chains
- Use `with` for file handles, database connections, locks, and temporary resources
- Use `pathlib.Path` over `os.path` for all file path manipulation
- Use f-strings for all string interpolation
- `@dataclass` for data containers, Pydantic `BaseModel` when validation needed
- PEP 8 naming: `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants
- Prefer early returns to reduce nesting
