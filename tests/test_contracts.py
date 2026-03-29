#!/usr/bin/env python3
"""Layer 3: Contract tests for agent output protocol parsing.

Tests that the orchestrator's output parsing logic correctly handles all
documented agent output formats — SUCCESS/FAILURE from implementer,
PASS/FAIL from reviewer, TOKEN_REPORT blocks, and build/test script output.

Uses golden fixtures from tests/fixtures/. No external dependencies.

Usage:
    python3 tests/test_contracts.py [-v]
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# --- Parsers (extracted from orchestrator's implicit parsing logic) ---


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
        details = []
        files = []
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
        suggestions = []
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("---TOKEN_REPORT---"):
                break
            if stripped:
                suggestions.append(stripped)
        return {"status": "PASS", "suggestions": suggestions}

    elif first_line == "FAIL":
        issues = []
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


# --- Test Cases ---


class TestImplementerProtocol(unittest.TestCase):
    def test_success_output(self) -> None:
        fixture = (FIXTURES_DIR / "implementer-success.txt").read_text()
        result = parse_implementer_result(fixture)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("feat(", result["commit_message"])
        self.assertNotIn("TOKEN_REPORT", result["commit_message"])

    def test_failure_output(self) -> None:
        fixture = (FIXTURES_DIR / "implementer-failure.txt").read_text()
        result = parse_implementer_result(fixture)
        self.assertEqual(result["status"], "FAILURE")
        self.assertIn(result["reason"], ["BLOCKED", "BUILD_FAILED", "TESTS_FAILED", "COVERAGE_LOW"])
        self.assertTrue(len(result["details"]) > 0)
        self.assertTrue(len(result["files_modified"]) > 0)

    def test_success_has_token_report(self) -> None:
        fixture = (FIXTURES_DIR / "implementer-success.txt").read_text()
        report = parse_token_report(fixture)
        self.assertIsNotNone(report)
        self.assertIn("files_read", report)
        self.assertIn("tool_calls", report)
        self.assertIn("self_assessed_input", report)
        self.assertIn("self_assessed_output", report)

    def test_failure_has_token_report(self) -> None:
        fixture = (FIXTURES_DIR / "implementer-failure.txt").read_text()
        report = parse_token_report(fixture)
        self.assertIsNotNone(report)


class TestReviewerProtocol(unittest.TestCase):
    def test_pass_output(self) -> None:
        fixture = (FIXTURES_DIR / "reviewer-pass.txt").read_text()
        result = parse_reviewer_result(fixture)
        self.assertEqual(result["status"], "PASS")

    def test_fail_output(self) -> None:
        fixture = (FIXTURES_DIR / "reviewer-fail.txt").read_text()
        result = parse_reviewer_result(fixture)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(len(result["issues"]) > 0)
        for issue in result["issues"]:
            self.assertIn("severity", issue)
            self.assertIn(issue["severity"], ["CRITICAL", "HIGH"])
            self.assertIn("file", issue)
            self.assertIn("problem", issue)
            self.assertIn("fix", issue)

    def test_fail_has_optional_improvements(self) -> None:
        fixture = (FIXTURES_DIR / "reviewer-fail.txt").read_text()
        result = parse_reviewer_result(fixture)
        self.assertIn("optional_improvements", result)

    def test_pass_has_token_report(self) -> None:
        fixture = (FIXTURES_DIR / "reviewer-pass.txt").read_text()
        report = parse_token_report(fixture)
        self.assertIsNotNone(report)

    def test_fail_has_token_report(self) -> None:
        fixture = (FIXTURES_DIR / "reviewer-fail.txt").read_text()
        report = parse_token_report(fixture)
        self.assertIsNotNone(report)


class TestBuildOutput(unittest.TestCase):
    def test_success_output(self) -> None:
        fixture = (FIXTURES_DIR / "build-success.txt").read_text()
        result = parse_build_output(fixture)
        self.assertEqual(result["status"], "success")
        self.assertIsInstance(result["warnings"], int)

    def test_failure_output(self) -> None:
        fixture = (FIXTURES_DIR / "build-failure.txt").read_text()
        result = parse_build_output(fixture)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["errors"] > 0)


class TestTestOutput(unittest.TestCase):
    def test_success_output(self) -> None:
        fixture = (FIXTURES_DIR / "test-success.txt").read_text()
        result = parse_test_output(fixture)
        self.assertNotIn("error", result)
        self.assertEqual(result["failed"], 0)
        self.assertGreaterEqual(result["coverage"], 0.0)
        self.assertLessEqual(result["coverage"], 100.0)

    def test_failure_output(self) -> None:
        fixture = (FIXTURES_DIR / "test-failure.txt").read_text()
        result = parse_test_output(fixture)
        self.assertNotIn("error", result)
        self.assertGreater(result["failed"], 0)


class TestTokenReport(unittest.TestCase):
    def test_standalone_report(self) -> None:
        fixture = (FIXTURES_DIR / "token-report.txt").read_text()
        report = parse_token_report(fixture)
        self.assertIsNotNone(report)
        self.assertTrue(len(report["files_read"]) > 0)
        self.assertTrue(len(report["tool_calls"]) > 0)
        self.assertIn("self_assessed_input", report)
        self.assertIn("self_assessed_output", report)

    def test_missing_report_returns_none(self) -> None:
        output = "SUCCESS\n\nfeat(core): add thing"
        report = parse_token_report(output)
        self.assertIsNone(report)

    def test_malformed_report_returns_partial(self) -> None:
        output = "PASS\n---TOKEN_REPORT---\nFILES_READ:\n- src/app.py (~1200 chars)\n---END_TOKEN_REPORT---"
        report = parse_token_report(output)
        self.assertIsNotNone(report)
        self.assertEqual(len(report["files_read"]), 1)


class TestTokenAnalysisResult(unittest.TestCase):
    def test_no_findings(self) -> None:
        result = parse_token_analysis_result("FINDINGS: NONE")
        self.assertEqual(result["status"], "none")

    def test_findings_filed(self) -> None:
        output = "FINDINGS: FILED\nhttps://github.com/org/repo/issues/42"
        result = parse_token_analysis_result(output)
        self.assertEqual(result["status"], "filed")
        self.assertIn("github.com", result["url"])


class TestOpenPRResult(unittest.TestCase):
    def test_pr_info_parsed(self) -> None:
        output = "PR_BRANCH: feat/add-feature\nPR_NUMBER: 42\nPR_URL: https://github.com/org/repo/pull/42"
        result = parse_open_pr_result(output)
        self.assertEqual(result["branch"], "feat/add-feature")
        self.assertEqual(result["number"], "42")
        self.assertIn("github.com", result["url"])


class TestEdgeCases(unittest.TestCase):
    def test_empty_implementer_output(self) -> None:
        result = parse_implementer_result("")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_empty_reviewer_output(self) -> None:
        result = parse_reviewer_result("")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_empty_build_output(self) -> None:
        result = parse_build_output("")
        self.assertEqual(result["status"], "unknown")

    def test_empty_test_output(self) -> None:
        result = parse_test_output("")
        self.assertIn("error", result)

    def test_implementer_with_extra_whitespace(self) -> None:
        output = "  SUCCESS  \n\nfeat(core): add feature\n\n---TOKEN_REPORT---\nFILES_READ:\n---END_TOKEN_REPORT---"
        result = parse_implementer_result(output)
        self.assertEqual(result["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
