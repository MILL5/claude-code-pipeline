"""Compute a composite score from a metrics dict.

Correctness: weighted average of test-suite pass rates (per spec.md weights).
Efficiency: tokens + wall time vs. baseline (1.0 if no baseline).
Composite: 0.7 * correctness + 0.3 * efficiency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINES_DIR = PIPELINE_ROOT / "benchmarks" / "baselines"

SCORING_WEIGHTS = {
    "property": 0.5,
    "unit":     0.2,
    "discovery": 0.3,  # was "functional contract" in spec — module + CLI exist = pipeline produced something
}


def _suite_pct(suite_result: dict[str, Any], key_total: str = "total", key_pass: str = "passed") -> float:
    """Extract a 0-1 pass rate from a suite result. Returns 0 on errors."""
    if not suite_result or "error" in suite_result:
        return 0.0
    total = suite_result.get(key_total, 0)
    passed = suite_result.get(key_pass, 0)
    if not total:
        return 0.0
    return passed / total


def _correctness(metrics: dict[str, Any]) -> float:
    tests = metrics.get("tests", {})
    prop = tests.get("property", {})
    unit = tests.get("unit", {})

    prop_pct = _suite_pct(prop, "total_run", "total_passed")
    unit_pct = _suite_pct(unit, "total", "passed")

    # Discovery: if either suite ran successfully (not "error"), the module was discoverable.
    discovery = 0.0 if (prop.get("error") and unit.get("error")) else 1.0

    score = (
        SCORING_WEIGHTS["property"] * prop_pct
        + SCORING_WEIGHTS["unit"] * unit_pct
        + SCORING_WEIGHTS["discovery"] * discovery
    )
    return round(score, 4)


def _load_baseline(benchmark: str) -> dict[str, Any] | None:
    p = BASELINES_DIR / f"{benchmark}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _input_tokens(metrics: dict[str, Any]) -> int:
    """Total input tokens regardless of log format. Stream-json uses `total_input`,
    text fallback uses `total_input_estimate`."""
    tokens = metrics.get("tokens", {})
    return int(tokens.get("total_input") or tokens.get("total_input_estimate") or 0)


def _efficiency(metrics: dict[str, Any]) -> float:
    """1.0 = matches baseline. >1.0 = better (cheaper/faster). <1.0 = regressed."""
    baseline = _load_baseline(metrics.get("benchmark", ""))
    if baseline is None:
        return 1.0  # no baseline yet; don't penalize

    base_wall = baseline.get("wall_time_seconds", 0) or 1
    base_tokens = _input_tokens(baseline) or 1

    wall = metrics.get("wall_time_seconds", 0) or 1
    tokens = _input_tokens(metrics) or 1

    wall_ratio = base_wall / wall if wall else 1.0
    token_ratio = base_tokens / tokens if tokens else 1.0
    # Average; clip to a reasonable range so a single outlier doesn't dominate
    eff = (wall_ratio + token_ratio) / 2
    return round(max(0.1, min(eff, 3.0)), 4)


def score(metrics: dict[str, Any]) -> dict[str, float]:
    correctness = _correctness(metrics)
    efficiency = _efficiency(metrics)
    composite = round(0.7 * correctness + 0.3 * min(efficiency, 1.0), 4)
    return {
        "correctness": correctness,
        "efficiency": efficiency,
        "composite": composite,
    }
