# Python Implementer Rules

## Code Quality Rules (Rule 4)

Within the boundaries of what the brief asks for, write clean Python:

### Type Hints (PEP 484)
- Add type annotations to all function signatures (parameters and return types)
- Use `from __future__ import annotations` for forward references (Python < 3.10)
- Prefer `X | Y` union syntax over `Union[X, Y]` when targeting Python 3.10+
- Use `collections.abc` types for parameter hints (`Sequence`, `Mapping`, `Iterable`) and concrete types for return hints (`list`, `dict`)
- Annotate class variables and instance variables in `__init__`
- Use `TypeVar` for generic functions, `ParamSpec` for decorator signatures
- Never use `Any` without a comment explaining why it's necessary

### Docstrings (PEP 257)
- Module-level docstrings for every module explaining its purpose
- Class docstrings describing the class's role and key behaviors
- Function/method docstrings for all public API: one-line summary, then Args/Returns/Raises sections for non-trivial functions
- Use triple double-quotes (`"""`) consistently

### Data Containers
- Use `@dataclass` for plain data containers (prefer `frozen=True` when immutable)
- Use Pydantic `BaseModel` when validation or serialization is needed
- Use `TypedDict` for typed dictionary schemas (API responses, config dicts)
- Use `NamedTuple` for lightweight immutable records
- Never pass raw `dict` where a structured type would be clearer

### Exception Handling
- Catch specific exception types, never bare `except:` or `except Exception:`
- Use custom exception classes for domain-specific errors (inherit from a project base exception)
- Include context in exception messages: `raise ValueError(f"Invalid user_id={user_id}: must be positive")`
- Use `raise ... from e` to preserve exception chains
- Clean up resources in `finally` blocks or use context managers

### Context Managers
- Use `with` for file handles, database connections, locks, and temporary resources
- Implement `__enter__`/`__exit__` or use `@contextmanager` for custom resource management
- Prefer `contextlib.suppress(ExceptionType)` over empty except blocks

### String Formatting
- Use f-strings for all string interpolation
- Use `.format()` only when the template is defined separately from the data
- Never use `%` formatting or string concatenation for interpolation

### Path Handling
- Use `pathlib.Path` over `os.path` for all file path manipulation
- Use `/` operator for path joining: `base_dir / "subdir" / "file.txt"`
- Use `.resolve()` for absolute paths, `.exists()` / `.is_file()` for checks

### Import Organization
- Group imports in this order, separated by blank lines:
  1. Standard library (`os`, `sys`, `pathlib`, `typing`)
  2. Third-party packages (`fastapi`, `pydantic`, `sqlalchemy`)
  3. Local/project imports (`from myapp.models import User`)
- Use absolute imports; avoid relative imports except within a package's internal modules
- Never use `from module import *`

## Project Conventions

Key conventions for Python projects (the context brief overrides these if different):
- Follow PEP 8 naming: `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants
- Use `logging` module instead of `print()` for operational output
- Prefer composition over inheritance
- Use `enum.Enum` for fixed sets of values
- Prefer `functools.lru_cache` or `@cache` for memoization over manual caching
- Use `__all__` in `__init__.py` to define public API
- Keep functions short (under 30 lines as a guideline)
- Prefer early returns to reduce nesting
