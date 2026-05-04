# Pipeline Benchmarks

Regression benchmarks for the orchestration pipeline. Each benchmark runs a
*frozen* feature request through the pipeline and scores the produced code
against an objective oracle (property tests + unit tests). Same input + same
oracle = changes in score reflect changes in the pipeline.

## Why this exists

`tests/validate_structure.py` confirms the pipeline can run. The contract
tests confirm agents emit the right output format. Neither answers
"did the pipeline produce *correct* code?" That's what the benchmarks here are for.

## Running Tier 1

The Tier 1 benchmark (`tier1-base64`) asks the pipeline to implement RFC 4648
base64 encode/decode. The oracle is a round-trip property suite:
`decode(encode(x)) == x` for 1000 random inputs, plus reference equivalence
against Python's stdlib `base64`.

### Modes

The harness supports three modes for invoking the pipeline:

| Mode | Use when | Cost |
|------|----------|------|
| `manual`   | You want to drive `/orchestrate` interactively and have the harness score the result | Just your time + Claude tokens |
| `auto`     | Headless run — `claude -p` invokes the pipeline non-interactively | API tokens (~$1-5/run) |
| `existing` | You already have a project dir with a candidate implementation; just score it | Free |

### Quick start (manual mode — recommended for first run)

```bash
python3 benchmarks/scripts/run_benchmark.py tier1-base64 --mode=manual
```

The harness will:
1. Copy the skeleton into a temp dir, `git init` it, run `init.sh`
2. Print the path and pause — you `cd` there, open Claude Code, run `/orchestrate`
3. Press ENTER when finished
4. Harness runs the property + unit tests against the produced code
5. Writes `benchmarks/runs/<id>/metrics.json`

### Score-only mode (no pipeline run)

```bash
python3 benchmarks/scripts/run_benchmark.py tier1-base64 \
    --mode=existing --project-dir=/path/to/finished/project
```

Useful for testing the harness itself, or for scoring a hand-written reference
implementation to seed a baseline.

## Setting a baseline

After a representative run produces good metrics:

```bash
cp benchmarks/runs/<run_id>/metrics.json benchmarks/baselines/tier1-base64.json
```

The baseline is the reference for `compare_runs.py` and for the efficiency
component of subsequent run scores.

## Comparing runs

```bash
# Compare a run to its baseline
python3 benchmarks/scripts/compare_runs.py benchmarks/runs/<run_id>

# Compare two runs head-to-head
python3 benchmarks/scripts/compare_runs.py runs/<run_a> runs/<run_b>
```

Exits 1 if correctness drops by more than `REGRESSION_THRESHOLD` (currently 0.05).

## Metrics schema

`metrics.json` shape (abridged):

```json
{
  "run_id": "20260503-141022-f657850-tier1-base64",
  "benchmark": "tier1-base64",
  "pipeline_sha": "f657850",
  "mode": "manual",
  "wall_time_seconds": 247,
  "tokens": {
    "total_input_estimate": 53000,
    "total_output_estimate": 13200,
    "report_count": 7
  },
  "pipeline": {"waves": 2, "review_fail_rounds": 0, "bug_fix_cycles": 0},
  "code_delta": {"files_changed": 3, "lines_added": 187, "lines_deleted": 0},
  "tests": {
    "property": {"total_passed": 5000, "total_run": 5000, "pass_pct": 100.0, "...": "..."},
    "unit":     {"passed": 8, "total": 8, "pass_pct": 100.0, "...": "..."}
  },
  "score": {"correctness": 1.0, "efficiency": 1.04, "composite": 0.91}
}
```

Token capture is best-effort: it parses `---TOKEN_REPORT---` blocks from the
session log. In `--mode=manual`, save the session transcript to
`benchmarks/runs/<id>/pipeline.log` to populate token metrics; otherwise they
default to zero and only correctness is meaningful.

## Statistical handling (planned, not yet implemented)

LLM output is non-deterministic. A single run can swing 5-10% on tokens or
wall time. The first iteration of the harness runs once; future work is to
support `--runs=N` for repeated runs with mean + stddev. Until then, treat
single-run scores as noisy.

## Adding a new benchmark

A benchmark is a directory under `benchmarks/<name>/` with this layout:

```
<name>/
  feature-request.md   # frozen pipeline input
  spec.md              # acceptance contract — used by the scorer, NOT given to the pipeline
  skeleton/            # minimal project the pipeline runs in
    CLAUDE.md
    ORCHESTRATOR.md
    pyproject.toml     # or whatever stack config
    src/
  fixtures/
    property_tests.py  # round-trip / metamorphic oracle
    unit_tests.py      # spec-derived unit tests
    _discover.py       # helper to find pipeline-produced module
```

The `_discover.py` pattern lets the pipeline name files freely without the
fixtures penalizing naming choices.

## Phase 2 (future)

- **Consumer-diag mode**: when invoked from a consuming repo, layer that
  repo's `.claude/local/*.md` overlays into the harness so the benchmark
  measures local-context impact (helping vs. hurting baseline).
- **Statistical mode**: `--runs=N` with mean ± stddev gating.
- **Mutation testing**: separate tool that mutates pipeline prompts and
  re-runs benchmarks to identify load-bearing prompt sections. See
  the GitHub issue tagged `mutation-testing`.
