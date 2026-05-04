#!/usr/bin/env python3
"""Run N benchmark iterations and report noise-floor statistics (mean ± stddev).

Usage:
    python3 benchmarks/scripts/noise_floor.py tier1-base64 --n=5
    python3 benchmarks/scripts/noise_floor.py tier1-base64 --n=5 --orchestrator-model=sonnet
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_SCRIPT = PIPELINE_ROOT / "benchmarks" / "scripts" / "run_benchmark.py"


def _run_one(benchmark: str, orchestrator_model: str, run_index: int) -> dict[str, Any] | None:
    print(f"\n{'='*60}")
    print(f"RUN {run_index}: {benchmark} (orchestrator={orchestrator_model})")
    print(f"{'='*60}")

    cmd = [
        sys.executable, str(RUN_SCRIPT),
        benchmark,
        "--mode=auto",
        f"--orchestrator-model={orchestrator_model}",
    ]
    proc = subprocess.run(
        cmd, cwd=PIPELINE_ROOT, capture_output=False, text=True, timeout=7200,
    )

    # run_benchmark.py prints "Metrics written: <path>"
    # We reconstruct the path from runs/ dir by taking the most recent
    # metrics.json (reliable since runs are sequential)
    runs_dir = PIPELINE_ROOT / "benchmarks" / "runs"
    candidates = sorted(
        runs_dir.glob(f"*-{benchmark}/metrics.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        print(f"  ERROR: no metrics.json found for run {run_index}")
        return None

    metrics_path = candidates[0]
    try:
        return json.loads(metrics_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ERROR reading {metrics_path}: {e}")
        return None


def _input_tokens(m: dict[str, Any]) -> int:
    t = m.get("tokens", {})
    return int(t.get("total_input") or t.get("total_input_estimate") or 0)


def _stats(values: list[float]) -> tuple[float, float]:
    """Return (mean, stddev). stddev=0 for n<=1."""
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return mean, math.sqrt(variance)


def _fmt(mean: float, std: float, precision: int = 3) -> str:
    fmt = f".{precision}f"
    return f"{mean:{fmt}} ± {std:{fmt}}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("benchmark", default="tier1-base64", nargs="?")
    p.add_argument("--n", type=int, default=5, help="Number of runs (default: 5)")
    p.add_argument("--orchestrator-model", default="sonnet",
                   choices=["sonnet", "opus", "haiku"])
    args = p.parse_args()

    results: list[dict[str, Any]] = []
    for i in range(1, args.n + 1):
        m = _run_one(args.benchmark, args.orchestrator_model, i)
        if m is not None:
            results.append(m)
            sc = m.get("score", {})
            print(f"  → correctness={sc.get('correctness', 0):.3f}  "
                  f"efficiency={sc.get('efficiency', 0):.3f}  "
                  f"composite={sc.get('composite', 0):.3f}  "
                  f"wall={m.get('wall_time_seconds', 0)}s  "
                  f"tokens={_input_tokens(m):,}")

    n = len(results)
    if n == 0:
        print("\nNo successful runs — cannot compute stats.")
        return 1

    correctness  = [r.get("score", {}).get("correctness", 0.0) for r in results]
    efficiency   = [r.get("score", {}).get("efficiency", 0.0)  for r in results]
    composite    = [r.get("score", {}).get("composite", 0.0)   for r in results]
    wall_times   = [float(r.get("wall_time_seconds", 0))       for r in results]
    tokens       = [float(_input_tokens(r))                     for r in results]
    prop_rates   = [r.get("tests", {}).get("property", {}).get("total_passed", 0) /
                    max(r.get("tests", {}).get("property", {}).get("total_run", 1), 1)
                    for r in results]
    unit_rates   = [r.get("tests", {}).get("unit", {}).get("passed", 0) /
                    max(r.get("tests", {}).get("unit", {}).get("total", 1), 1)
                    for r in results]

    print(f"\n{'='*60}")
    print(f"NOISE FLOOR  n={n}  benchmark={args.benchmark}  orchestrator={args.orchestrator_model}")
    print(f"{'='*60}")
    print(f"  correctness   {_fmt(*_stats(correctness))}")
    print(f"  efficiency    {_fmt(*_stats(efficiency))}")
    print(f"  composite     {_fmt(*_stats(composite))}")
    print(f"  wall_time (s) {_fmt(*_stats(wall_times), precision=0)}")
    print(f"  tokens (in)   {_fmt(*_stats(tokens), precision=0)}")
    print(f"  prop pass%    {_fmt(*_stats(prop_rates))}")
    print(f"  unit pass%    {_fmt(*_stats(unit_rates))}")
    print()
    print("Per-run correctness:", "  ".join(f"{v:.3f}" for v in correctness))
    print("Per-run wall_time:  ", "  ".join(f"{int(v)}s" for v in wall_times))
    print()

    # Save summary alongside the metrics
    summary = {
        "n": n,
        "benchmark": args.benchmark,
        "orchestrator_model": args.orchestrator_model,
        "run_ids": [r.get("run_id", "?") for r in results],
        "stats": {
            "correctness":  {"mean": _stats(correctness)[0],  "std": _stats(correctness)[1]},
            "efficiency":   {"mean": _stats(efficiency)[0],   "std": _stats(efficiency)[1]},
            "composite":    {"mean": _stats(composite)[0],    "std": _stats(composite)[1]},
            "wall_seconds": {"mean": _stats(wall_times)[0],   "std": _stats(wall_times)[1]},
            "input_tokens": {"mean": _stats(tokens)[0],       "std": _stats(tokens)[1]},
            "prop_pass_rate": {"mean": _stats(prop_rates)[0], "std": _stats(prop_rates)[1]},
            "unit_pass_rate": {"mean": _stats(unit_rates)[0], "std": _stats(unit_rates)[1]},
        },
    }
    out = PIPELINE_ROOT / "benchmarks" / "runs" / f"noise_floor_{args.benchmark}_n{n}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"Summary saved: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
