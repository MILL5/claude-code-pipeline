# Python Architect Context

## Project Context

This is a Python project. When planning, account for:
- Package/module structure and import graph — circular imports are a common failure mode
- Virtual environment and dependency management (pip, poetry, uv, pdm)
- Python version constraints (3.9+ for modern typing, 3.10+ for match/case, 3.11+ for ExceptionGroup)
- The 4-file rule: tasks touching more than 3 files must be split into smaller tasks

## Module/Package Decomposition Patterns

When planning tasks that involve Python modules and packages, account for their specific complexity:

- **Single module changes** (Haiku): Adding a function to an existing module, updating a dataclass, adding a new route handler, writing a utility function
- **Cross-module design** (Sonnet): Defining a new package structure, designing the import graph between modules, creating shared protocol/ABC hierarchies, refactoring circular dependencies
- **New package from scratch** (Sonnet): `__init__.py` exports, public API surface design, re-export strategy

## Async Patterns

- **Simple async function** (Haiku): A single `async def` that awaits one or two things
- **Async pipeline/orchestration** (Sonnet): `asyncio.gather`, `TaskGroup`, cancellation handling, structured concurrency patterns
- **Event-driven architecture** (Sonnet/Opus): Custom event loops, signal handling, graceful shutdown, connection pool lifecycle

## Framework-Specific Patterns

### Django
- **Views, serializers, simple models** (Haiku): CRUD endpoints, model fields, admin registration
- **Middleware, signals, custom managers** (Sonnet): Request/response lifecycle hooks, cross-cutting concerns, complex querysets
- **Migration logic, multi-db routing** (Sonnet/Opus): Data migrations, database router design, tenant isolation

### FastAPI
- **Route handlers, response models** (Haiku): Endpoint functions with Pydantic models
- **Dependency injection, middleware** (Sonnet): Custom `Depends()` chains, authentication flows, request lifecycle
- **Background tasks, WebSocket handlers** (Sonnet): Long-running processes, connection management, pub/sub patterns

### CLI (Click/Typer/argparse)
- **Individual commands** (Haiku): A single CLI command with its options and arguments
- **Command groups, plugin architecture** (Sonnet): Nested command hierarchies, dynamic command loading, shared context

## Data Pipeline Patterns

- **Single transform step** (Haiku): A function that reads, transforms, and writes data
- **Multi-stage pipeline** (Sonnet): DAG of processing steps, error handling strategy, retry logic
- **Streaming/chunked processing** (Sonnet): Generator-based pipelines, backpressure, memory-bounded processing

## Python-Specific Decomposition Notes

- Module boundaries are natural Haiku boundaries — define the interface (Sonnet if non-trivial), then implement each module as a separate Haiku task
- Abstract Base Classes (ABCs) and Protocol classes define contracts — designing the protocol is Sonnet, implementing each concrete class is Haiku
- Decorator design is Sonnet (especially with arguments and type preservation); applying existing decorators is Haiku
- Configuration management (settings module, env vars, secrets) is Sonnet for the design, Haiku for adding individual settings
