# ORCHESTRATOR.md

> Living architecture reference. Updated at the end of each orchestration session.

## Project Overview

**Name:** base64bench
**Stack:** python
**Description:** Benchmark fixture project. The pipeline is asked to add a base64 module here, and its output is scored on correctness (round-trip property tests) and efficiency (tokens, time, waves).

## Targets / Entry Points

| Target | Platform | Description |
|--------|----------|-------------|
| base64bench | Python 3.9+ | Library + CLI module |

## Directory Structure

```
src/             # implementation goes here
pyproject.toml   # project config
```

## Architecture

Library-first. Pure-Python implementation of standard base64 (RFC 4648). A small CLI wraps it.

## Key Services / Modules

| Service | Responsibility | File(s) |
|---------|---------------|---------|
| (to be added) | base64 encode/decode | src/ |

## Conventions

### Naming
- Snake_case functions and modules.

### Patterns
- Pure functions; no global state.
- Type hints on all public APIs.

### Error Handling
- Raise `ValueError` with a clear message for invalid base64 input.

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

- Do NOT call `base64` from the standard library — implement encode/decode from scratch using bit operations on the alphabet. (The benchmark exists to measure what the pipeline produces; wrapping `base64` defeats it.)

## Current State

- **Last updated:** initial
- **Build status:** clean
- **Test status:** no tests yet
- **Open work:** add base64 encode/decode module per feature-request.md
