# ORCHESTRATOR.md

> Living architecture reference. Updated at the end of each orchestration session.

## Project Overview

**Name:** lrubench
**Stack:** python
**Description:** Benchmark fixture project. The pipeline is asked to add a fixed-capacity LRU cache here, and its output is scored on correctness (reference-parity property tests + edge-case unit tests) and efficiency (tokens, time, waves).

## Targets / Entry Points

| Target | Platform | Description |
|--------|----------|-------------|
| lrubench | Python 3.9+ | Library |

## Directory Structure

```
src/             # implementation goes here
pyproject.toml   # project config
```

## Architecture

Library-only. Pure-Python implementation of a fixed-capacity LRU cache with
O(1) `get`/`put`. No CLI.

## Key Services / Modules

| Service | Responsibility | File(s) |
|---------|---------------|---------|
| (to be added) | LRU cache | src/ |

## Conventions

### Naming
- Snake_case for modules; PascalCase for classes (e.g., `LRUCache`).

### Patterns
- Pure data structure; no global state.
- Type hints on all public APIs.

### Error Handling
- `LRUCache(capacity <= 0)` raises `ValueError`.
- `cache.get(missing_key)` raises `KeyError`.

## Testing

### Structure
- Test files: `test_*.py` at project root
- Use pytest

### Coverage Requirements
- Minimum: 90% for new code

## Known Fragile Areas

| Area | Risk | Mitigation |
|------|------|------------|
| (none yet) | | |

## Anti-Patterns (Do NOT)

- Do NOT import `OrderedDict` from `collections` or use `functools.lru_cache` — implement the eviction structure from scratch (hash map + doubly-linked list, or equivalent O(1) design). The benchmark exists to measure what the pipeline produces; reusing a stdlib LRU defeats it.

## Current State

- **Last updated:** initial
- **Build status:** clean
- **Test status:** no tests yet
- **Open work:** add LRU cache class per feature-request.md
