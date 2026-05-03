#!/usr/bin/env python3
"""Measure orchestrator's static load contribution.

Computes the bytes/tokens the orchestrator loads at /orchestrate entry,
and per-step cumulative load. Used as ROI proof for context-optimization
PRs (issue #78).

Source of truth for entry-load files: skills/orchestrate/SKILL.md
"Prerequisites" (lines 17-22) and "Step 0: Load Adapters" (lines 53-110).
If those sections change, update the ENTRY_FILES list below.

Token estimate: char count / 4 (Unicode code points after UTF-8 decode).
Real BPE tokenization differs by ~10-20%; sufficient for relative measurement.

Baseline JSON schema v1:
    {
      "schema_version": 1,
      "git_sha": "<HEAD sha>",
      "adapter": "python",
      "discovery_mode": "steps_dir | skill_md_headings",
      "measurements": {
        "initial_load": {"chars": N, "est_tokens": N},
        "step_<id>": {"cumulative_chars": N, "delta_chars": N,
                       "est_tokens": N},
        ...
        "total": {"chars": N, "est_tokens": N}
      }
    }

Exit codes:
    0  success
    1  error (missing required file, schema mismatch, etc.)
    2  budget exceeded (--budget flag only)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent

# Files the orchestrator reads at /orchestrate entry.
# Source: skills/orchestrate/SKILL.md "Prerequisites" + "Step 0: Load Adapters"
ENTRY_FILES = [
    "skills/orchestrate/SKILL.md",
    "templates/ORCHESTRATOR.md.template",
    "templates/CLAUDE.md.template",
    "templates/pipeline.config.template",
]

STEP_HEADING_RE = re.compile(r"^### Step ([\w.]+)\b", re.MULTILINE)


def chars_to_tokens(chars: int) -> int:
    return chars // 4


def read_required(rel_path: str) -> str:
    """Read a pipeline-managed file or exit 1 with descriptive stderr."""
    path = PIPELINE_ROOT / rel_path
    if not path.exists():
        sys.stderr.write(
            f"ERROR: required file missing: {rel_path}\n"
            f"  resolved to: {path}\n"
        )
        sys.exit(1)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"ERROR: cannot read {rel_path}: {exc}\n")
        sys.exit(1)


def discover_steps() -> tuple[list[tuple[str, Path | None]], str]:
    """Discover step IDs and their files.

    Priority:
        1. If skills/orchestrate/steps/ exists, enumerate its *.md files.
        2. Else, parse ### Step headings from skills/orchestrate/SKILL.md.

    Returns (steps, mode):
        steps: list of (step_id, step_file_path_or_none).
            Pre-Lever-1, all step_file values are None (steps inlined).
        mode: "steps_dir" or "skill_md_headings".
    """
    steps_dir = PIPELINE_ROOT / "skills" / "orchestrate" / "steps"
    if steps_dir.is_dir():
        files = sorted(steps_dir.glob("*.md"))
        steps: list[tuple[str, Path | None]] = []
        for f in files:
            # Filename like "1a-clarify.md" -> step_id "1a"
            step_id = f.stem.split("-", 1)[0]
            steps.append((step_id, f))
        return steps, "steps_dir"

    content = read_required("skills/orchestrate/SKILL.md")
    step_ids = STEP_HEADING_RE.findall(content)
    return [(sid, None) for sid in step_ids], "skill_md_headings"


def get_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PIPELINE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def measure(adapter: str) -> dict:
    """Compute the measurement dict matching baseline JSON schema v1."""
    initial_chars = 0
    for rel in ENTRY_FILES:
        initial_chars += len(read_required(rel))

    overlay_rel = f"adapters/{adapter}/architect-overlay.md"
    overlay_path = PIPELINE_ROOT / overlay_rel
    if not overlay_path.exists():
        sys.stderr.write(
            f"ERROR: adapter overlay not found: {overlay_rel}\n"
            f"  resolved to: {overlay_path}\n"
            f"  available adapters: "
            f"{', '.join(sorted(p.name for p in (PIPELINE_ROOT / 'adapters').iterdir() if p.is_dir()))}\n"
        )
        sys.exit(1)
    initial_chars += len(read_required(overlay_rel))

    measurements: dict[str, dict[str, int]] = {
        "initial_load": {
            "chars": initial_chars,
            "est_tokens": chars_to_tokens(initial_chars),
        },
    }

    steps, mode = discover_steps()
    cumulative = initial_chars
    for step_id, step_file in steps:
        if step_file is not None:
            try:
                step_text = step_file.read_text(encoding="utf-8")
            except OSError as exc:
                sys.stderr.write(
                    f"ERROR: cannot read step file {step_file}: {exc}\n"
                )
                sys.exit(1)
            delta = len(step_text)
        else:
            # Pre-Lever-1: step is inlined in SKILL.md (already counted)
            delta = 0
        cumulative += delta
        measurements[f"step_{step_id}"] = {
            "cumulative_chars": cumulative,
            "delta_chars": delta,
            "est_tokens": chars_to_tokens(cumulative),
        }

    measurements["total"] = {
        "chars": cumulative,
        "est_tokens": chars_to_tokens(cumulative),
    }

    return {
        "schema_version": 1,
        "git_sha": get_git_sha(),
        "adapter": adapter,
        "discovery_mode": mode,
        "measurements": measurements,
    }


def _step_label(step_id: str, mode: str, steps: list[tuple[str, Path | None]]) -> str:
    if mode == "steps_dir":
        for sid, fp in steps:
            if sid == step_id and fp is not None:
                return f"+steps/{fp.name}"
        return "+steps/(missing)"
    return "+(inline in SKILL — pre-Lever-1)"


def print_table(data: dict, compare: dict | None) -> None:
    measurements = data["measurements"]
    mode = data["discovery_mode"]
    steps, _ = discover_steps()

    headers = ["Step", "Loaded", "Chars", "Est. Tokens"]
    if compare is not None:
        headers.append("Δ Tokens")

    rows: list[list[str]] = []

    init = measurements["initial_load"]
    init_label = "SKILL.md, ORCH.tmpl, CLAUDE.tmpl, pipeline.config, adapter overlay"
    row = ["initial", init_label, f"{init['chars']:,}", f"{init['est_tokens']:,}"]
    if compare is not None:
        prev = compare["measurements"]["initial_load"]["est_tokens"]
        row.append(f"{init['est_tokens'] - prev:+,}")
    rows.append(row)

    for key, val in measurements.items():
        if not key.startswith("step_"):
            continue
        step_id = key[len("step_"):]
        loaded = _step_label(step_id, mode, steps)
        row = [
            step_id,
            loaded,
            f"{val['cumulative_chars']:,}",
            f"{val['est_tokens']:,}",
        ]
        if compare is not None:
            prev_entry = compare["measurements"].get(key)
            if prev_entry is None:
                row.append("(new)")
            else:
                row.append(f"{val['est_tokens'] - prev_entry['est_tokens']:+,}")
        rows.append(row)

    total = measurements["total"]
    row = ["total", "—", f"{total['chars']:,}", f"{total['est_tokens']:,}"]
    if compare is not None:
        prev = compare["measurements"]["total"]["est_tokens"]
        row.append(f"{total['est_tokens'] - prev:+,}")
    rows.append(row)

    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "  ".join("-" * w for w in widths)

    print(fmt.format(*headers))
    print(sep)
    for r in rows:
        print(fmt.format(*r))

    sha_short = data["git_sha"][:8] if data["git_sha"] != "unknown" else "unknown"
    print()
    print(
        f"discovery_mode: {data['discovery_mode']}  "
        f"adapter: {data['adapter']}  "
        f"git_sha: {sha_short}"
    )


def load_compare(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(f"ERROR: --compare file not found: {path}\n")
        sys.exit(1)
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: cannot parse --compare file {path}: {exc}\n")
        sys.exit(1)
    if data.get("schema_version") != 1:
        sys.stderr.write(
            f"ERROR: schema_version mismatch in {path} "
            f"(got {data.get('schema_version')!r}, expected 1)\n"
        )
        sys.exit(1)
    return data


def write_baseline(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\nBaseline written to {path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure orchestrator's static load contribution.",
    )
    parser.add_argument(
        "--adapter",
        default="python",
        help="Adapter name for overlay sample (default: python).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Write current measurement to FILE as JSON.",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        help="Read prior baseline JSON, print delta column.",
    )
    parser.add_argument(
        "--budget",
        type=int,
        help="Fail with exit 2 if initial load exceeds INT tokens.",
    )
    args = parser.parse_args()

    data = measure(args.adapter)
    compare_data = load_compare(args.compare) if args.compare else None
    print_table(data, compare_data)

    if args.baseline:
        write_baseline(args.baseline, data)

    if args.budget is not None:
        initial_tokens = data["measurements"]["initial_load"]["est_tokens"]
        if initial_tokens > args.budget:
            sys.stderr.write(
                f"BUDGET EXCEEDED: initial load {initial_tokens:,} tok "
                f"> {args.budget:,} tok budget\n"
            )
            sys.exit(2)


if __name__ == "__main__":
    main()
