#!/usr/bin/env python3
"""Compare two benchmark metrics.json files (or one against a frozen baseline).

Usage:
    python3 benchmarks/scripts/compare_runs.py <run_a> <run_b>
    python3 benchmarks/scripts/compare_runs.py <run_dir>            # vs. baseline
    python3 benchmarks/scripts/compare_runs.py --baseline=tier1-base64 <run_dir>

Exit codes:
    0 — no significant regression
    1 — significant regression (correctness mean drops > REGRESSION_THRESHOLD)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINES_DIR = PIPELINE_ROOT / "benchmarks" / "baselines"

# A correctness drop greater than this is treated as a regression
REGRESSION_THRESHOLD = 0.05


def _load(path_or_name: str) -> dict[str, Any]:
    """Load a metrics.json. Accepts: a run dir, a metrics.json path, or a baseline name."""
    p = Path(path_or_name)
    if p.is_dir():
        p = p / "metrics.json"
    if not p.exists():
        # Try as a baseline name
        candidate = BASELINES_DIR / f"{path_or_name}.json"
        if candidate.exists():
            return json.loads(candidate.read_text())
        raise FileNotFoundError(f"Cannot resolve metrics file for: {path_or_name}")
    return json.loads(p.read_text())


def _delta(a: float, b: float) -> str:
    diff = b - a
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.3f}"


def _fmt_int(a: int, b: int) -> str:
    diff = b - a
    sign = "+" if diff >= 0 else ""
    pct = f" ({sign}{100 * diff / a:.1f}%)" if a else ""
    return f"{a:>8} → {b:<8}  ({sign}{diff}){pct}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_a", help="First metrics.json or run dir (or omit for baseline)")
    p.add_argument("run_b", nargs="?", default=None,
                   help="Second metrics.json or run dir; if omitted, run_a is compared to its baseline")
    p.add_argument("--baseline", default=None,
                   help="Force a specific baseline name (overrides metrics.benchmark)")
    args = p.parse_args()

    if args.run_b is None:
        # Single arg: compare run_a to its baseline
        b = _load(args.run_a)
        baseline_name = args.baseline or b.get("benchmark", "")
        try:
            a = _load(baseline_name)
            label_a = f"baseline:{baseline_name}"
        except FileNotFoundError:
            print(f"No baseline found for {baseline_name!r}; nothing to compare against.")
            print("Tip: copy a metrics.json into benchmarks/baselines/<benchmark>.json to set one.")
            return 0
        label_b = f"run:{b.get('run_id', '?')}"
    else:
        a = _load(args.run_a)
        b = _load(args.run_b)
        label_a = a.get("run_id", args.run_a)
        label_b = b.get("run_id", args.run_b)

    print(f"A: {label_a}")
    print(f"B: {label_b}")
    print()

    a_score = a.get("score", {})
    b_score = b.get("score", {})

    print("Score:")
    for k in ("correctness", "efficiency", "composite"):
        av = a_score.get(k, 0.0)
        bv = b_score.get(k, 0.0)
        print(f"  {k:<12} {av:.3f} → {bv:.3f}   ({_delta(av, bv)})")

    print()
    print("Wall time (seconds):")
    print(f"  {_fmt_int(a.get('wall_time_seconds', 0), b.get('wall_time_seconds', 0))}")

    print()
    print("Tokens:")
    a_tokens = a.get("tokens", {})
    b_tokens = b.get("tokens", {})
    a_tok = a_tokens.get("total_input") or a_tokens.get("total_input_estimate") or 0
    b_tok = b_tokens.get("total_input") or b_tokens.get("total_input_estimate") or 0
    print(f"  input           {_fmt_int(a_tok, b_tok)}")
    a_cache = a_tokens.get("total_cache_read", 0)
    b_cache = b_tokens.get("total_cache_read", 0)
    if a_cache or b_cache:
        print(f"  cache_read      {_fmt_int(a_cache, b_cache)}")

    print()
    print("Pipeline:")
    pipeline_keys = ("waves", "review_fail_rounds", "bug_fix_cycles",
                     "turns", "tool_calls", "agent_spawns", "sendmessage_calls")
    for k in pipeline_keys:
        av = a.get("pipeline", {}).get(k, 0)
        bv = b.get("pipeline", {}).get(k, 0)
        print(f"  {k:<22} {_fmt_int(av, bv)}")

    print()
    print("Code delta:")
    for k in ("files_changed", "lines_added", "lines_deleted"):
        av = a.get("code_delta", {}).get(k, 0)
        bv = b.get("code_delta", {}).get(k, 0)
        print(f"  {k:<16} {_fmt_int(av, bv)}")

    # Gate
    correctness_drop = a_score.get("correctness", 0.0) - b_score.get("correctness", 0.0)
    if correctness_drop > REGRESSION_THRESHOLD:
        print()
        print(f"REGRESSION: correctness dropped by {correctness_drop:.3f} (threshold {REGRESSION_THRESHOLD})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
