# Pipeline Self-Tests

Tests for the pipeline itself, not for consumer projects. Run from the pipeline repo root.

## Layers

| Layer | Script | Purpose |
|-------|--------|---------|
| 1 | `validate_structure.py` | Structural integrity (~277 checks, auto-scales). |
| 2 | _planned_ | Dry-run prompt-composition validation. |
| 3 | `test_contracts.py` | Output protocol contract tests (51 tests). |
| 4 | `smoke/run_smoke.py` | Bootstrap smoke test (`init.sh` + scripts). `--full` for end-to-end pipeline (~$0.50–$1.00 in API tokens). |

## Measurement

`measure_orchestrator_load.py` — static measurement of the orchestrator's entry-load. Reports the bytes/tokens loaded at `/orchestrate` entry plus per-step cumulative load. No API calls; runs in milliseconds. Used as ROI proof for context-optimization PRs (issue #78).

```bash
# Default: print measurement table
python3 tests/measure_orchestrator_load.py

# Write baseline JSON
python3 tests/measure_orchestrator_load.py --baseline tests/baselines/orchestrator-load.json

# Compare current state against a baseline (prints Δ Tokens column)
python3 tests/measure_orchestrator_load.py --compare tests/baselines/orchestrator-load.json

# CI gate: fail if initial load exceeds N tokens
python3 tests/measure_orchestrator_load.py --budget 18500

# Use a different adapter overlay (default: python)
python3 tests/measure_orchestrator_load.py --adapter swift-ios
```

**Exit codes:** `0` success · `1` error (missing file, schema mismatch) · `2` `--budget` exceeded.

**Token estimate:** `chars / 4`. Real BPE tokenization differs by ~10–20%; sufficient for relative measurement.

**Baseline file:** `tests/baselines/orchestrator-load.json` is the committed pre-Lever-1 baseline. Update it as part of any PR that intentionally changes the orchestrator's entry-load.

## Quick reference

```bash
python3 tests/validate_structure.py
python3 tests/test_contracts.py
python3 tests/smoke/run_smoke.py
python3 tests/smoke/run_smoke.py --full         # API costs apply
python3 tests/measure_orchestrator_load.py
```
