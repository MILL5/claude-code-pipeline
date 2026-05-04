"""Best-effort extraction of pipeline metrics from a session log.

The log is whatever stdout the pipeline emitted. Two formats are supported:

1. **Stream-JSON** (`--output-format stream-json`, used by --mode=auto): newline-
   delimited JSON events including tool calls, subagent results, and per-message
   token usage. Preferred — yields trustworthy token counts and turn-level detail.
2. **Plain text** (--mode=manual transcripts, or older runs): falls back to regex
   parsing of `---TOKEN_REPORT---` blocks and surface heuristics. Less precise.

Missing fields default to None or zero rather than raising.
"""

from __future__ import annotations

import json
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


def _is_stream_json(text: str) -> bool:
    """Stream-JSON output starts with one or more '{...}' lines."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        return line.startswith("{")
    return False


def _capture_stream_json(text: str) -> dict[str, Any]:
    """Parse stream-json transcript: aggregate token usage, count tool calls, count subagents."""
    total_input = 0
    total_output = 0
    total_cache_read = 0
    cache_creation = 0
    tool_calls = 0
    agent_spawns = 0
    sendmessage_calls = 0
    turns = 0
    by_model: dict[str, dict[str, int]] = {}

    for raw in text.splitlines():
        raw = raw.strip()
        if not raw or not raw.startswith("{"):
            continue
        try:
            evt = json.loads(raw)
        except json.JSONDecodeError:
            continue

        evt_type = evt.get("type", "")
        if evt_type == "assistant" or evt_type == "user":
            turns += 1

        # Per-message usage rolls up under the assistant event in stream-json
        msg = evt.get("message", {}) if isinstance(evt.get("message"), dict) else {}
        usage = msg.get("usage", {}) if isinstance(msg.get("usage"), dict) else {}
        if usage:
            total_input += int(usage.get("input_tokens", 0) or 0)
            total_output += int(usage.get("output_tokens", 0) or 0)
            total_cache_read += int(usage.get("cache_read_input_tokens", 0) or 0)
            cache_creation += int(usage.get("cache_creation_input_tokens", 0) or 0)
            model = msg.get("model", "unknown")
            slot = by_model.setdefault(model, {"input": 0, "output": 0, "cache_read": 0})
            slot["input"] += int(usage.get("input_tokens", 0) or 0)
            slot["output"] += int(usage.get("output_tokens", 0) or 0)
            slot["cache_read"] += int(usage.get("cache_read_input_tokens", 0) or 0)

        # Tool use events
        content = msg.get("content", []) if isinstance(msg.get("content"), list) else []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_calls += 1
                name = block.get("name", "")
                if name == "Agent":
                    agent_spawns += 1
                elif name == "SendMessage":
                    sendmessage_calls += 1

    return {
        "log_present": True,
        "log_format": "stream-json",
        "tokens": {
            "total_input": total_input,
            "total_output": total_output,
            "total_cache_read": total_cache_read,
            "total_cache_creation": cache_creation,
            "by_model": by_model,
        },
        "pipeline": {
            "turns": turns,
            "tool_calls": tool_calls,
            "agent_spawns": agent_spawns,
            "sendmessage_calls": sendmessage_calls,
        },
    }


def capture(log_path: Path) -> dict[str, Any]:
    if not log_path.exists():
        return {"tokens": {}, "pipeline": {}, "log_present": False}

    text = log_path.read_text(errors="replace")
    if _is_stream_json(text):
        return _capture_stream_json(text)

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
        "log_format": "text",
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
