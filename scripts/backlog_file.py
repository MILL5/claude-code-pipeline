#!/usr/bin/env python3
"""Backlog filing utility for /orchestrate phases.

Detects opt-in via .github/pipeline-backlog.yml, renders an issue body from
a body_context dict, and files the issue via `gh issue create` with the
canonical label set (type:*, priority:*, source:*).

Callable two ways:
  CLI:  python3 scripts/backlog_file.py \
            --title "Extract common error mapper" \
            --type chore --priority p2 \
            --body-context-json '{"phase":"reviewer","pr_number":"42",...}'
  Lib:  from backlog_file import file_backlog_issue
        result = file_backlog_issue(title=..., type=..., priority=..., body_context=...)

Never raises on the happy path — returns a structured IssueResult so callers
can log-and-continue without blowing up an /orchestrate run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

VALID_TYPES = {"bug", "feature", "chore", "docs"}
VALID_PRIORITIES = {"p0", "p1", "p2"}
SENTINEL_PATH = ".github/pipeline-backlog.yml"
GH_TIMEOUT = 30


@dataclass
class IssueResult:
    status: str  # "filed" | "skipped" | "failed"
    url: Optional[str] = None
    number: Optional[int] = None
    reason: Optional[str] = None


def find_repo_root(start: Path) -> Optional[Path]:
    path = start.resolve()
    while path != path.parent:
        if (path / ".git").exists():
            return path
        path = path.parent
    return None


def read_sentinel(repo_root: Path) -> Optional[dict]:
    """Return parsed sentinel dict, or None if absent/invalid."""
    sentinel = repo_root / SENTINEL_PATH
    if not sentinel.exists():
        return None
    text = sentinel.read_text()
    if yaml is not None:
        try:
            parsed = yaml.safe_load(text)
            return parsed if isinstance(parsed, dict) else None
        except yaml.YAMLError:
            return None
    return _parse_minimal_yaml(text)


def _parse_minimal_yaml(text: str) -> dict:
    """Fallback parser for the sentinel's flat key:value schema.

    Handles booleans, ints, nulls, and quoted strings. Ignores comments and
    indented blocks (the sentinel is intentionally flat). Good enough when
    PyYAML is unavailable.
    """
    out: dict = {}
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") or ":" not in stripped:
            continue
        if raw.startswith((" ", "\t")):
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.split("#", 1)[0].strip()
        if val in ("", "null", "~"):
            out[key] = None
        elif val in ("true", "True"):
            out[key] = True
        elif val in ("false", "False"):
            out[key] = False
        else:
            try:
                out[key] = int(val)
            except ValueError:
                out[key] = val.strip("'\"")
    return out


def render_body(body_context: dict) -> str:
    """Render the chore issue body with D8 traceability block.

    Expected keys in body_context (all optional — missing values render as
    placeholders so the issue is still filable):
      phase, pr_number, run_id, reasoning, summary, context, acceptance
    """
    pr = body_context.get("pr_number")
    pr_line = f"#{pr}" if pr else "(pre-PR — no PR number yet)"
    summary = (body_context.get("summary") or "").strip()
    context = (body_context.get("context") or "").strip()
    phase = body_context.get("phase", "unknown")
    run_id = body_context.get("run_id", "unknown")
    reasoning = (body_context.get("reasoning") or "").strip()
    acceptance = (body_context.get("acceptance") or "").strip()

    lines = [
        "## Summary",
        summary or "_(no summary provided)_",
        "",
        "## Context",
        context or "_(no additional context)_",
        "",
        "## Origin",
        f"**Deferred from:** {pr_line}",
        f"**Phase:** {phase}",
        f"**Run ID:** {run_id}",
        f"**Reasoning:** {reasoning or '_(not provided)_'}",
    ]
    if acceptance:
        lines += ["", "## Acceptance", acceptance]
    return "\n".join(lines) + "\n"


def _run_gh(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=GH_TIMEOUT)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"gh invocation failed: {e}"
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, result.stdout.strip()


def gh_issue_create(title: str, body: str, labels: list[str]) -> tuple[bool, str]:
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    for label in labels:
        cmd += ["--label", label]
    return _run_gh(cmd)


def gh_project_item_add(project_number: int, issue_url: str) -> tuple[bool, str]:
    return _run_gh(["gh", "project", "item-add", str(project_number), "--url", issue_url])


def file_backlog_issue(
    title: str,
    type: str,
    priority: str,
    body_context: dict,
    source: str = "ai-deferred",
    repo_root: Optional[Path] = None,
) -> IssueResult:
    if type not in VALID_TYPES:
        return IssueResult(status="failed", reason=f"invalid type: {type!r}")
    if priority not in VALID_PRIORITIES:
        return IssueResult(status="failed", reason=f"invalid priority: {priority!r}")

    root = repo_root or find_repo_root(Path.cwd())
    if root is None:
        return IssueResult(status="skipped", reason="not in a git repo")

    sentinel = read_sentinel(root)
    if sentinel is None:
        return IssueResult(
            status="skipped",
            reason="backlog integration not enabled for this repo — run /bootstrap-backlog to enable",
        )
    if not sentinel.get("enabled", True):
        return IssueResult(status="skipped", reason="backlog integration disabled in sentinel")

    body = render_body(body_context)
    labels = [f"type: {type}", f"priority: {priority}", f"source: {source}"]

    ok, out = gh_issue_create(title, body, labels)
    if not ok:
        ok2, out2 = gh_issue_create(title, body, [f"type: {type}", f"priority: {priority}"])
        if not ok2:
            return IssueResult(status="failed", reason=out2)
        out = out2

    url = out
    number: Optional[int] = None
    try:
        number = int(url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        pass

    project_number = sentinel.get("project_number")
    if project_number:
        gh_project_item_add(int(project_number), url)

    return IssueResult(status="filed", url=url, number=number)


def _cli() -> None:
    ap = argparse.ArgumentParser(description="File a pipeline backlog issue via gh CLI.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--type", required=True, choices=sorted(VALID_TYPES))
    ap.add_argument("--priority", required=True, choices=sorted(VALID_PRIORITIES))
    ap.add_argument(
        "--body-context-json",
        required=True,
        help="JSON-encoded body_context dict "
             "(phase, pr_number, run_id, reasoning, summary, context, acceptance).",
    )
    ap.add_argument("--source", default="ai-deferred")
    args = ap.parse_args()

    try:
        body_context = json.loads(args.body_context_json)
    except json.JSONDecodeError as e:
        print(f"invalid --body-context-json: {e}", file=sys.stderr)
        sys.exit(2)

    result = file_backlog_issue(
        title=args.title,
        type=args.type,
        priority=args.priority,
        body_context=body_context,
        source=args.source,
    )
    print(json.dumps(asdict(result)))
    sys.exit(1 if result.status == "failed" else 0)


if __name__ == "__main__":
    _cli()
