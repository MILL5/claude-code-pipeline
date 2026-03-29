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


def parse_reviewer_result(output: str) -> dict:
    """Parse code-reviewer agent output per the documented protocol."""
    lines = output.strip().split("\n")
    if not lines:
        return {"status": "UNKNOWN", "error": "empty output"}

    first_line = lines[0].strip()
    if first_line == "PASS":
        suggestions: list[str] = []
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("---TOKEN_REPORT---"):
                break
            if stripped:
                suggestions.append(stripped)
        return {"status": "PASS", "suggestions": suggestions}

    elif first_line == "FAIL":
        issues: list[dict] = []
        current_issue: dict = {}
        optional_improvements: list[str] = []
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
                    optional_improvements.append(stripped)
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
    """Extract TOKEN_REPORT block from any agent output."""
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

    section = None
    for line in block.split("\n"):
        stripped = line.strip()
        if stripped == "FILES_READ:":
            section = "files"
        elif stripped == "TOOL_CALLS:":
            section = "tools"
        elif stripped.startswith("SELF_ASSESSED_INPUT:"):
            report["self_assessed_input"] = stripped.split(":", 1)[1].strip()
            section = None
        elif stripped.startswith("SELF_ASSESSED_OUTPUT:"):
            report["self_assessed_output"] = stripped.split(":", 1)[1].strip()
            section = None
        elif section == "files" and stripped.startswith("- "):
            report["files_read"].append(stripped[2:])
        elif section == "tools" and stripped.startswith("- "):
            parts = stripped[2:].split(":", 1)
            if len(parts) == 2:
                report["tool_calls"][parts[0].strip()] = parts[1].strip()

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
