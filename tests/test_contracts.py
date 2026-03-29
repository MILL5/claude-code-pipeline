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

import sys
import unittest
from pathlib import Path

# Allow running from repo root or tests/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parsers import (
    parse_build_output,
    parse_defect_report,
    parse_defect_reports,
    parse_implementer_result,
    parse_open_pr_result,
    parse_reviewer_result,
    parse_test_output,
    parse_token_analysis_result,
    parse_token_report,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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


class TestDefectReportParsing(unittest.TestCase):
    def test_critical_report(self) -> None:
        fixture = (FIXTURES_DIR / "defect-report-critical.txt").read_text()
        result = parse_defect_report(fixture)
        self.assertIsNotNone(result)
        self.assertNotIn("error", result)
        self.assertEqual(result["severity"], "CRITICAL")
        self.assertEqual(result["component"], "authentication flow")
        self.assertEqual(result["found_in"], "src/auth/login.ts")
        self.assertTrue(len(result["steps"]) >= 3)
        self.assertIn("login", result["steps"][0].lower())
        self.assertTrue(len(result["expected"]) > 0)
        self.assertIn("TypeError", result["actual"])
        self.assertEqual(len(result["screenshots"]), 2)
        self.assertIn("Browser/Device", result["environment"])
        self.assertTrue(len(result["additional_context"]) > 0)

    def test_high_report(self) -> None:
        fixture = (FIXTURES_DIR / "defect-report-high.txt").read_text()
        result = parse_defect_report(fixture)
        self.assertIsNotNone(result)
        self.assertNotIn("error", result)
        self.assertEqual(result["severity"], "HIGH")
        self.assertEqual(result["component"], "dashboard charts")
        self.assertTrue(len(result["steps"]) >= 3)
        self.assertEqual(len(result["screenshots"]), 1)

    def test_medium_report_minimal(self) -> None:
        fixture = (FIXTURES_DIR / "defect-report-medium.txt").read_text()
        result = parse_defect_report(fixture)
        self.assertIsNotNone(result)
        self.assertNotIn("error", result)
        self.assertEqual(result["severity"], "MEDIUM")
        self.assertTrue(len(result["steps"]) >= 3)
        # No screenshots in this report
        self.assertEqual(len(result["screenshots"]), 0)

    def test_invalid_report_missing_fields(self) -> None:
        fixture = (FIXTURES_DIR / "defect-report-invalid.txt").read_text()
        result = parse_defect_report(fixture)
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertIn("expected", result["error"])
        self.assertIn("actual", result["error"])

    def test_not_a_report_returns_none(self) -> None:
        fixture = (FIXTURES_DIR / "defect-report-not-a-report.txt").read_text()
        result = parse_defect_report(fixture)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self) -> None:
        result = parse_defect_report("")
        self.assertIsNone(result)


class TestDefectReportsBatch(unittest.TestCase):
    def test_multiple_reports_sorted_by_severity(self) -> None:
        comments = [
            {"id": 100, "body": (FIXTURES_DIR / "defect-report-high.txt").read_text(),
             "user": {"login": "tester1"}},
            {"id": 101, "body": (FIXTURES_DIR / "defect-report-critical.txt").read_text(),
             "user": {"login": "tester2"}},
            {"id": 102, "body": (FIXTURES_DIR / "defect-report-medium.txt").read_text(),
             "user": {"login": "tester1"}},
        ]
        defects = parse_defect_reports(comments)
        self.assertEqual(len(defects), 3)
        # CRITICAL should be first
        self.assertEqual(defects[0]["severity"], "CRITICAL")
        self.assertEqual(defects[0]["author"], "tester2")
        self.assertEqual(defects[0]["comment_id"], 101)
        # HIGH second
        self.assertEqual(defects[1]["severity"], "HIGH")
        # MEDIUM third
        self.assertEqual(defects[2]["severity"], "MEDIUM")
        # Sequential IDs
        self.assertEqual(defects[0]["id"], 1)
        self.assertEqual(defects[1]["id"], 2)
        self.assertEqual(defects[2]["id"], 3)

    def test_non_report_comments_filtered(self) -> None:
        comments = [
            {"id": 200, "body": "LGTM! Looks good to me.", "user": {"login": "reviewer"}},
            {"id": 201, "body": (FIXTURES_DIR / "defect-report-high.txt").read_text(),
             "user": {"login": "tester"}},
            {"id": 202, "body": "Can we also add dark mode?", "user": {"login": "pm"}},
        ]
        defects = parse_defect_reports(comments)
        self.assertEqual(len(defects), 1)
        self.assertEqual(defects[0]["severity"], "HIGH")

    def test_invalid_reports_sorted_to_end(self) -> None:
        comments = [
            {"id": 300, "body": (FIXTURES_DIR / "defect-report-invalid.txt").read_text(),
             "user": {"login": "tester1"}},
            {"id": 301, "body": (FIXTURES_DIR / "defect-report-high.txt").read_text(),
             "user": {"login": "tester2"}},
        ]
        defects = parse_defect_reports(comments)
        self.assertEqual(len(defects), 2)
        # Valid HIGH report first, invalid report last
        self.assertEqual(defects[0]["severity"], "HIGH")
        self.assertIn("error", defects[1])

    def test_empty_comments_list(self) -> None:
        defects = parse_defect_reports([])
        self.assertEqual(len(defects), 0)


if __name__ == "__main__":
    unittest.main()
