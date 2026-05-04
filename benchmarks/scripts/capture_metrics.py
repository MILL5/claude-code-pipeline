"""Best-effort extraction of pipeline metrics from a session log.

The log is whatever stdout the pipeline emitted (claude -p output, or a saved
manual transcript). Parsing is regex-based and lenient — missing fields default
to None or zero rather than raising. Refine over time.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TOKEN_REPORT_RE = re.compile(
    r"-{3,}\s*TOKEN_REPORT\s*-{3,}(.*?)(?=-{3,}|$)",
    re.DOTALL | re.IGNORECASE,
)
KV_RE = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*(.+?)\s*$", re.MULTILINE)
WAVE_RE = re.compile(r"\b[Ww]ave\s+(\d+)\b")
REVIEW_FAIL_RE = re.compile(r"\b(?:review[_\s]fail|FAIL\s*\(review\))\b", re.IGNORECASE)
BUG_FIX_RE = re.compile(r"\bbug[_\s]?fix(?:\s+cycle)?\b", re.IGNORECASE)


def _parse_token_report(block: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for m in KV_RE.finditer(block):
        key = m.group(1).strip()
        val = m.group(2).strip()
        # Try numeric coercion
        try:
            if "." in val:
                out[key] = float(val)
            else:
                out[key] = int(val)
        except ValueError:
            out[key] = val
    return out


def capture(log_path: Path) -> dict[str, Any]:
    if not log_path.exists():
        return {"tokens": {}, "pipeline": {}, "log_present": False}

    text = log_path.read_text(errors="replace")

    # Parse TOKEN_REPORT blocks
    reports = [_parse_token_report(m.group(1)) for m in TOKEN_REPORT_RE.finditer(text)]

    # Aggregate tokens
    total_input = sum(r.get("input_tokens", r.get("estimated_tokens", 0)) for r in reports)
    total_output = sum(r.get("output_tokens", 0) for r in reports)
    files_read = sum(r.get("files_read", 0) for r in reports)
    tool_calls = sum(r.get("tool_calls", 0) for r in reports)

    # Wave count: highest wave number mentioned (rough heuristic)
    wave_numbers = [int(m.group(1)) for m in WAVE_RE.finditer(text)]
    waves = max(wave_numbers) if wave_numbers else 0

    review_fails = len(REVIEW_FAIL_RE.findall(text))
    bug_fix_cycles = len(BUG_FIX_RE.findall(text))

    return {
        "log_present": True,
        "tokens": {
            "total_input_estimate": total_input,
            "total_output_estimate": total_output,
            "files_read_total": files_read,
            "tool_calls_total": tool_calls,
            "report_count": len(reports),
        },
        "pipeline": {
            "waves": waves,
            "review_fail_rounds": review_fails,
            "bug_fix_cycles": bug_fix_cycles,
        },
        "raw_reports": reports,  # kept for debugging
    }
