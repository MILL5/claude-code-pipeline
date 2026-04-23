## Summary
Extract common error mapper for Grok client

## Context
Reviewer surfaced duplicated error-to-user-message mapping in 4 files during
wave 2. A single mapper keeps the UX consistent when the API changes.

## Origin
**Deferred from:** #42
**Phase:** reviewer
**Run ID:** 20260423-181000
**Reasoning:** Cross-cuts 4 files, adds new abstraction — Sonnet-tier.

## Acceptance
A `GrokErrorMapper` class under `src/tools/grok_client.py` with unit tests; callers refactored to use it.
