"""Shared parsers for pipeline agent and script output protocols.

These parsers implement the orchestrator's implicit parsing logic for
agent outputs (SUCCESS/FAILURE, PASS/FAIL, TOKEN_REPORT) and build/test
script outputs. Used by contract tests and available for smoke test
checkpoint validation.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import re


def parse_implementer_result(output: str) -> dict:
    """Parse implementer agent output per the documented protocol."""
    lines = output.strip().split("\n")
    if not lines:
        return {"status": "UNKNOWN", "error": "empty output"}

    first_line = lines[0].strip()
    if first_line == "SUCCESS":
        # Extract commit message (everything after first blank line)
        commit_msg = ""
        body_start = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "" and body_start is None:
                body_start = i + 1
            elif body_start is not None:
                if line.strip().startswith("---TOKEN_REPORT---"):
                    break
                commit_msg += line + "\n"
        return {"status": "SUCCESS", "commit_message": commit_msg.strip()}

    elif first_line == "FAILURE":
        reason = ""
        details: list[str] = []
        files: list[str] = []
        section = None
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("---TOKEN_REPORT---"):
                break
            if stripped.startswith("REASON:"):
                reason = stripped.split(":", 1)[1].strip()
                section = "reason"
            elif stripped == "DETAILS:":
                section = "details"
            elif stripped == "FILES_MODIFIED:":
                section = "files"
            elif section == "details" and stripped:
                details.append(stripped)
            elif section == "files" and stripped:
                files.append(stripped)
        return {
            "status": "FAILURE",
            "reason": reason,
            "details": details,
            "files_modified": files,
        }
    else:
        return {"status": "UNKNOWN", "error": f"unexpected first line: {first_line}"}


def _parse_optional_entry(raw: str) -> dict:
    """Split a `[should-fix] ...` / `[nice-to-have] ...` prefix from free text.

    Returns {"text": str, "tag": "should-fix"|"nice-to-have"|None}. Entries
    without a known tag get tag=None for backward compatibility.
    """
    s = raw.strip()
    for tag in ("should-fix", "nice-to-have"):
        prefix = f"[{tag}]"
        if s.startswith(prefix):
            return {"text": s[len(prefix):].strip(), "tag": tag}
    return {"text": s, "tag": None}


def parse_reviewer_result(output: str) -> dict:
    """Parse code-reviewer agent output per the documented protocol."""
    lines = output.strip().split("\n")
    if not lines:
        return {"status": "UNKNOWN", "error": "empty output"}

    first_line = lines[0].strip()
    if first_line == "PASS":
        suggestions: list[dict] = []
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("---TOKEN_REPORT---"):
                break
            if stripped:
                suggestions.append(_parse_optional_entry(stripped))
        return {"status": "PASS", "suggestions": suggestions}

    elif first_line == "FAIL":
        issues: list[dict] = []
        current_issue: dict = {}
        optional_improvements: list[dict] = []
        in_optional = False
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("---TOKEN_REPORT---"):
                break
            if stripped == "--- OPTIONAL IMPROVEMENTS ---":
                if current_issue:
                    issues.append(current_issue)
                    current_issue = {}
                in_optional = True
                continue
            if in_optional:
                if stripped:
                    optional_improvements.append(_parse_optional_entry(stripped))
                continue
            if stripped.startswith("ISSUE:"):
                if current_issue:
                    issues.append(current_issue)
                current_issue = {"severity": stripped.split(":", 1)[1].strip()}
            elif stripped.startswith("FILE:"):
                current_issue["file"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("LINE:"):
                current_issue["line"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("PROBLEM:"):
                current_issue["problem"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("FIX:"):
                current_issue["fix"] = stripped.split(":", 1)[1].strip()
        if current_issue:
            issues.append(current_issue)
        return {
            "status": "FAIL",
            "issues": issues,
            "optional_improvements": optional_improvements,
        }
    else:
        return {"status": "UNKNOWN", "error": f"unexpected first line: {first_line}"}


def parse_token_report(output: str) -> dict | None:
    """Extract TOKEN_REPORT block from any agent output.

    Compact single-line-per-field format:
        ---TOKEN_REPORT---
        FILES_READ: <path1> ~Nchars; <path2> ~Nchars
        TOOL_CALLS: Read=N Write=N Edit=N build-runner=N
        ---END_TOKEN_REPORT---

    `FILES_READ` may be `(none)` when no files were read; `TOOL_CALLS` is required.
    """
    start_marker = "---TOKEN_REPORT---"
    end_marker = "---END_TOKEN_REPORT---"

    start_idx = output.find(start_marker)
    if start_idx == -1:
        return None

    end_idx = output.find(end_marker, start_idx)
    if end_idx == -1:
        return None

    block = output[start_idx + len(start_marker):end_idx].strip()
    report: dict = {"files_read": [], "tool_calls": {}}

    for line in block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("FILES_READ:"):
            payload = stripped.split(":", 1)[1].strip()
            if payload and payload.lower() != "(none)":
                report["files_read"] = [
                    entry.strip()
                    for entry in payload.split(";")
                    if entry.strip()
                ]
        elif stripped.startswith("TOOL_CALLS:"):
            payload = stripped.split(":", 1)[1].strip()
            for token in payload.split():
                if "=" in token:
                    name, count = token.split("=", 1)
                    report["tool_calls"][name.strip()] = count.strip()

    return report


def parse_build_output(output: str) -> dict:
    """Parse build script output per the documented contract."""
    lines = output.strip().split("\n")
    summary_line = lines[-1] if lines else ""

    if "BUILD SUCCEEDED" in summary_line:
        match = re.search(r"(\d+)\s+warning", summary_line)
        warnings = int(match.group(1)) if match else 0
        return {"status": "success", "warnings": warnings}
    elif "BUILD FAILED" in summary_line:
        error_match = re.search(r"(\d+)\s+error", summary_line)
        warn_match = re.search(r"(\d+)\s+warning", summary_line)
        errors = int(error_match.group(1)) if error_match else 0
        warnings = int(warn_match.group(1)) if warn_match else 0
        return {"status": "failed", "errors": errors, "warnings": warnings}
    else:
        return {"status": "unknown", "raw": summary_line}


def parse_test_output(output: str) -> dict:
    """Parse test script output per the documented contract."""
    summary_re = re.compile(
        r"Summary:\s*Total:\s*(\d+),\s*Passed:\s*(\d+),\s*Failed:\s*(\d+)"
        r"\s*\|\s*Coverage:\s*([\d.]+)%"
    )
    match = summary_re.search(output)
    if match:
        return {
            "total": int(match.group(1)),
            "passed": int(match.group(2)),
            "failed": int(match.group(3)),
            "coverage": float(match.group(4)),
        }
    return {"error": "summary line not found"}


def parse_token_analysis_result(output: str) -> dict:
    """Parse token-analysis skill output."""
    stripped = output.strip()
    if stripped == "FINDINGS: NONE":
        return {"status": "none"}
    elif stripped.startswith("FINDINGS: FILED"):
        lines = stripped.split("\n")
        url = lines[1].strip() if len(lines) > 1 else ""
        return {"status": "filed", "url": url}
    return {"status": "unknown", "raw": stripped}


def parse_open_pr_result(output: str) -> dict:
    """Parse open-pr skill output."""
    result: dict = {}
    for line in output.strip().split("\n"):
        if line.startswith("PR_BRANCH:"):
            result["branch"] = line.split(":", 1)[1].strip()
        elif line.startswith("PR_NUMBER:"):
            result["number"] = line.split(":", 1)[1].strip()
        elif line.startswith("PR_URL:"):
            result["url"] = line.split(":", 1)[1].strip()
    return result


def parse_plan_stub(output: str) -> dict | None:
    """Parse the architect-planner's PLAN_WRITTEN stub.

    Expected format (emitted by 1b agent on final plan output):
        PLAN_WRITTEN: .claude/tmp/1b-plan.md

        Summary:
        - Feature: <name>
        - Plan type: feat
        - Waves: 3 (sizes: 4, 3, 2)
        - Total tasks: 9
        - Models: 7 Haiku, 2 Sonnet, 0 Opus
        - Stacks: react, python
        - Estimated cost: $0.18
        - Implementation clarification: none

        Deferred items: 0
    """
    if "PLAN_WRITTEN:" not in output:
        return None

    result: dict = {"path": "", "deferred_items": 0}
    for line in output.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith("PLAN_WRITTEN:"):
            result["path"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- Feature:"):
            result["feature"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- Plan type:"):
            result["plan_type"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- Total tasks:"):
            try:
                result["total_tasks"] = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif stripped.startswith("- Waves:"):
            payload = stripped.split(":", 1)[1].strip()
            # "3 (sizes: 4, 3, 2)" -> waves=3, wave_sizes=[4,3,2]
            count_match = re.match(r"(\d+)", payload)
            if count_match:
                result["waves"] = int(count_match.group(1))
            sizes_match = re.search(r"sizes:\s*([\d,\s]+)", payload)
            if sizes_match:
                result["wave_sizes"] = [
                    int(s.strip()) for s in sizes_match.group(1).split(",")
                    if s.strip().isdigit()
                ]
        elif stripped.startswith("- Models:"):
            payload = stripped.split(":", 1)[1].strip()
            counts = {}
            for match in re.finditer(r"(\d+)\s+(Haiku|Sonnet|Opus)", payload):
                counts[match.group(2).lower()] = int(match.group(1))
            result["models"] = counts
        elif stripped.startswith("- Stacks:"):
            payload = stripped.split(":", 1)[1].strip()
            result["stacks"] = [s.strip() for s in payload.split(",") if s.strip()]
        elif stripped.startswith("- Estimated cost:"):
            payload = stripped.split(":", 1)[1].strip().lstrip("$")
            try:
                result["estimated_cost"] = float(payload)
            except ValueError:
                pass
        elif stripped.startswith("Deferred items:"):
            payload = stripped.split(":", 1)[1].strip()
            try:
                result["deferred_items"] = int(payload)
            except ValueError:
                pass

    return result


# --- Defect Report Parsing ---

_SEVERITY_VALUES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def parse_defect_report(comment_body: str) -> dict | None:
    """Parse a single GitHub PR comment as a defect report.

    Returns a dict with the parsed fields, or None if the comment does not
    contain a valid defect report header.
    """
    # Must contain the defect report header
    if "### DEFECT REPORT" not in comment_body.upper():
        return None

    lines = comment_body.split("\n")
    report: dict = {
        "severity": "",
        "component": "",
        "found_in": "",
        "steps": [],
        "expected": "",
        "actual": "",
        "screenshots": [],
        "environment": {},
        "additional_context": "",
    }

    section: str | None = None
    section_lines: list[str] = []

    def _flush_section() -> None:
        """Flush accumulated section lines into the report."""
        if not section:
            return
        text = "\n".join(section_lines).strip()
        if section == "steps":
            # Extract numbered list items
            report["steps"] = [
                m.group(1).strip()
                for m in re.finditer(r"^\d+\.\s+(.+)$", text, re.MULTILINE)
            ]
        elif section == "expected":
            report["expected"] = text
        elif section == "actual":
            report["actual"] = text
        elif section == "screenshots":
            report["screenshots"] = re.findall(
                r"!\[([^\]]*)\]\(([^)]+)\)", text
            )
        elif section == "environment":
            for m in re.finditer(
                r"\*\*([^*]+?)(?::\s*)?\*\*(?::)?\s*(.+)", text
            ):
                report["environment"][m.group(1).strip()] = m.group(2).strip()
        elif section == "additional_context":
            report["additional_context"] = text

    for line in lines:
        stripped = line.strip()

        # Inline fields (before sections)
        if stripped.startswith("**Severity:**"):
            val = stripped.split("**Severity:**", 1)[1].strip()
            # Handle "CRITICAL | HIGH | MEDIUM | LOW" template vs actual value
            if val in _SEVERITY_VALUES:
                report["severity"] = val
            elif "|" not in val:
                # Might be a severity with extra text
                for s in _SEVERITY_VALUES:
                    if s in val.upper():
                        report["severity"] = s
                        break
            continue
        if stripped.startswith("**Component:**"):
            report["component"] = stripped.split("**Component:**", 1)[1].strip()
            continue
        if stripped.startswith("**Found in:**"):
            report["found_in"] = stripped.split("**Found in:**", 1)[1].strip()
            continue

        # Section headers
        if stripped.lower().startswith("#### steps to reproduce"):
            _flush_section()
            section = "steps"
            section_lines = []
            continue
        if stripped.lower().startswith("#### expected behavior"):
            _flush_section()
            section = "expected"
            section_lines = []
            continue
        if stripped.lower().startswith("#### actual behavior"):
            _flush_section()
            section = "actual"
            section_lines = []
            continue
        if stripped.lower().startswith("#### screenshots"):
            _flush_section()
            section = "screenshots"
            section_lines = []
            continue
        if stripped.lower().startswith("#### environment"):
            _flush_section()
            section = "environment"
            section_lines = []
            continue
        if stripped.lower().startswith("#### additional context"):
            _flush_section()
            section = "additional_context"
            section_lines = []
            continue
        # New h4 section we don't recognize — stop current section
        if stripped.startswith("#### "):
            _flush_section()
            section = None
            section_lines = []
            continue

        if section is not None:
            section_lines.append(line)

    _flush_section()

    # Validation: required fields
    missing = []
    if not report["severity"]:
        missing.append("severity")
    if not report["steps"]:
        missing.append("steps")
    if not report["expected"]:
        missing.append("expected")
    if not report["actual"]:
        missing.append("actual")

    if missing:
        return {"error": f"missing required fields: {', '.join(missing)}", "partial": report}

    return report


def parse_defect_reports(comments: list[dict]) -> list[dict]:
    """Parse multiple GitHub API comment objects into defect reports.

    Each comment dict should have at least 'id' and 'body' keys
    (matching the GitHub API response shape).

    Returns a list of parsed defect reports sorted by severity
    (CRITICAL first), each augmented with 'comment_id' and 'author' fields.
    """
    defects: list[dict] = []
    for comment in comments:
        body = comment.get("body", "")
        parsed = parse_defect_report(body)
        if parsed is None:
            continue
        if "error" in parsed:
            # Include invalid reports so callers can reply with errors
            parsed["comment_id"] = comment.get("id", "")
            parsed["author"] = comment.get("user", {}).get("login", "")
            defects.append(parsed)
            continue
        parsed["comment_id"] = comment.get("id", "")
        parsed["author"] = comment.get("user", {}).get("login", "")
        defects.append(parsed)

    # Sort valid reports by severity (errors go to the end)
    def _sort_key(d: dict) -> tuple:
        if "error" in d:
            return (99, 0)
        return (_SEVERITY_ORDER.get(d["severity"], 99), 0)

    defects.sort(key=_sort_key)

    # Assign sequential IDs
    for i, d in enumerate(defects, 1):
        d["id"] = i

    return defects


# ---------------------------------------------------------------------------
# Azure / Bicep skill output parsers
# ---------------------------------------------------------------------------

def parse_cost_estimate_output(output: str) -> dict | None:
    """Parse azure-cost-estimate skill output.

    Expected format:
        COST ESTIMATE | Total: $X.XX/month
    """
    match = re.search(
        r"COST ESTIMATE\s*\|\s*Total:\s*\$([0-9,.]+)/month",
        output,
    )
    if not match:
        return None

    total_str = match.group(1).replace(",", "")
    try:
        total = float(total_str)
    except ValueError:
        return None

    return {"status": "estimated", "total_monthly": total}


def parse_security_scan_output(output: str) -> dict | None:
    """Parse security-scan skill output.

    Expected format:
        SECURITY SCAN | Total: N findings | Critical: N, High: N, Medium: N, Low: N
    """
    match = re.search(
        r"SECURITY SCAN\s*\|\s*Total:\s*(\d+)\s+findings?\s*\|\s*"
        r"Critical:\s*(\d+),\s*High:\s*(\d+),\s*Medium:\s*(\d+),\s*Low:\s*(\d+)",
        output,
    )
    if not match:
        return None

    return {
        "status": "scanned",
        "total": int(match.group(1)),
        "critical": int(match.group(2)),
        "high": int(match.group(3)),
        "medium": int(match.group(4)),
        "low": int(match.group(5)),
    }


def parse_drift_check_output(output: str) -> dict | None:
    """Parse azure-drift-check skill output.

    Expected format:
        DRIFT CHECK | Total: N resources | Drifted: N, Compliant: N, Missing: N
    """
    match = re.search(
        r"DRIFT CHECK\s*\|\s*Total:\s*(\d+)\s+resources?\s*\|\s*"
        r"Drifted:\s*(\d+),\s*Compliant:\s*(\d+),\s*Missing:\s*(\d+)",
        output,
    )
    if not match:
        return None

    return {
        "status": "checked",
        "total": int(match.group(1)),
        "drifted": int(match.group(2)),
        "compliant": int(match.group(3)),
        "missing": int(match.group(4)),
    }


def parse_deploy_bicep_output(output: str) -> dict | None:
    """Parse deploy-bicep skill output.

    Expected formats:
        DEPLOY SUCCEEDED | N resources created | N modified
        DEPLOY FAILED | <error summary>
    """
    success_match = re.search(
        r"DEPLOY SUCCEEDED\s*\|\s*(\d+)\s+resources?\s+created\s*\|\s*(\d+)\s+modified",
        output,
    )
    if success_match:
        return {
            "status": "succeeded",
            "created": int(success_match.group(1)),
            "modified": int(success_match.group(2)),
        }

    fail_match = re.search(r"DEPLOY FAILED\s*\|\s*(.+)", output)
    if fail_match:
        return {
            "status": "failed",
            "error": fail_match.group(1).strip(),
        }

    return None


def parse_azure_auth_output(output: str) -> dict | None:
    """Parse azure-login skill output.

    Expected formats:
        AZURE AUTH OK | Subscription: <name> (<id>) | User: <upn> | Method: <method>
        AZURE AUTH FAILED | <reason>
        AZURE AUTH WARNING | <message>
    """
    ok_match = re.search(
        r"AZURE AUTH OK\s*\|\s*Subscription:\s*(.+?)\s*\(([^)]+)\)\s*\|\s*User:\s*(\S+)\s*\|\s*Method:\s*(.+)",
        output,
    )
    if ok_match:
        return {
            "status": "ok",
            "subscription_name": ok_match.group(1).strip(),
            "subscription_id": ok_match.group(2).strip(),
            "user": ok_match.group(3).strip(),
            "method": ok_match.group(4).strip(),
        }

    fail_match = re.search(r"AZURE AUTH FAILED\s*\|\s*(.+)", output)
    if fail_match:
        return {
            "status": "failed",
            "reason": fail_match.group(1).strip(),
        }

    warn_match = re.search(r"AZURE AUTH WARNING\s*\|\s*(.+)", output)
    if warn_match:
        return {
            "status": "warning",
            "message": warn_match.group(1).strip(),
        }

    return None
