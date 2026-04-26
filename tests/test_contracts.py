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

import os
import sys
import unittest
from pathlib import Path

# Allow running from repo root or tests/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parsers import (
    parse_azure_auth_output,
    parse_build_output,
    parse_cost_estimate_output,
    parse_defect_report,
    parse_defect_reports,
    parse_deploy_bicep_output,
    parse_drift_check_output,
    parse_implementer_result,
    parse_open_pr_result,
    parse_plan_stub,
    parse_reviewer_result,
    parse_security_scan_output,
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
        self.assertGreater(len(report["files_read"]), 0)
        self.assertGreater(len(report["tool_calls"]), 0)
        # Self-assessed fields removed in compact format — orchestrator computes these.
        self.assertNotIn("self_assessed_input", report)
        self.assertNotIn("self_assessed_output", report)

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

    def test_tagged_optional_suggestions(self) -> None:
        fixture = (FIXTURES_DIR / "reviewer-pass-with-optional-tagged.txt").read_text()
        result = parse_reviewer_result(fixture)
        self.assertEqual(result["status"], "PASS")
        suggestions = result["suggestions"]
        self.assertEqual(len(suggestions), 2)
        tags = {s["tag"] for s in suggestions}
        self.assertEqual(tags, {"should-fix", "nice-to-have"})
        for s in suggestions:
            self.assertTrue(s["text"])
            self.assertFalse(s["text"].startswith("["))

    def test_untagged_entries_preserve_null_tag(self) -> None:
        fixture = (FIXTURES_DIR / "reviewer-fail.txt").read_text()
        result = parse_reviewer_result(fixture)
        for entry in result["optional_improvements"]:
            self.assertIn("tag", entry)
            self.assertIn("text", entry)


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


class TestBicepBuildOutput(unittest.TestCase):
    def test_bicep_build_success(self) -> None:
        fixture = (FIXTURES_DIR / "bicep-build-success.txt").read_text()
        result = parse_build_output(fixture)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["warnings"], 2)

    def test_bicep_build_failure(self) -> None:
        fixture = (FIXTURES_DIR / "bicep-build-failure.txt").read_text()
        result = parse_build_output(fixture)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"], 2)
        self.assertEqual(result["warnings"], 1)


class TestBicepTestOutput(unittest.TestCase):
    def test_bicep_test_success(self) -> None:
        fixture = (FIXTURES_DIR / "bicep-test-success.txt").read_text()
        result = parse_test_output(fixture)
        self.assertNotIn("error", result)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["total"], 18)
        self.assertGreaterEqual(result["coverage"], 0.0)

    def test_bicep_test_failure(self) -> None:
        fixture = (FIXTURES_DIR / "bicep-test-failure.txt").read_text()
        result = parse_test_output(fixture)
        self.assertNotIn("error", result)
        self.assertEqual(result["failed"], 3)
        self.assertEqual(result["total"], 18)


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
        # Compact format drops self-assessed input/output.
        self.assertNotIn("self_assessed_input", report)
        self.assertNotIn("self_assessed_output", report)

    def test_missing_report_returns_none(self) -> None:
        output = "SUCCESS\n\nfeat(core): add thing"
        report = parse_token_report(output)
        self.assertIsNone(report)

    def test_compact_format_parses(self) -> None:
        """Compact format: single-line FILES_READ and TOOL_CALLS."""
        output = (
            "PASS\n"
            "---TOKEN_REPORT---\n"
            "FILES_READ: src/app.py ~1200; src/util.py ~400\n"
            "TOOL_CALLS: Read=3 Grep=1\n"
            "---END_TOKEN_REPORT---"
        )
        report = parse_token_report(output)
        self.assertIsNotNone(report)
        self.assertEqual(len(report["files_read"]), 2)
        self.assertEqual(report["tool_calls"]["Read"], "3")
        self.assertEqual(report["tool_calls"]["Grep"], "1")

    def test_files_read_none_handled(self) -> None:
        """FILES_READ may be (none) when no files were read."""
        output = (
            "SUCCESS\n\nfix(core): tweak\n"
            "---TOKEN_REPORT---\n"
            "FILES_READ: (none)\n"
            "TOOL_CALLS: Edit=1\n"
            "---END_TOKEN_REPORT---"
        )
        report = parse_token_report(output)
        self.assertIsNotNone(report)
        self.assertEqual(report["files_read"], [])
        self.assertEqual(report["tool_calls"]["Edit"], "1")

    def test_no_self_assessed_fields_in_output(self) -> None:
        """Regression: SELF_ASSESSED_* fields should not appear in compact output."""
        for fixture_name in [
            "implementer-success.txt",
            "implementer-failure.txt",
            "reviewer-pass.txt",
            "reviewer-fail.txt",
            "token-report.txt",
        ]:
            content = (FIXTURES_DIR / fixture_name).read_text()
            self.assertNotIn("SELF_ASSESSED_INPUT", content,
                             f"{fixture_name} still has SELF_ASSESSED_INPUT")
            self.assertNotIn("SELF_ASSESSED_OUTPUT", content,
                             f"{fixture_name} still has SELF_ASSESSED_OUTPUT")


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


class TestPlanStub(unittest.TestCase):
    def test_plan_stub_full_parse(self) -> None:
        fixture = (FIXTURES_DIR / "plan-stub.txt").read_text()
        result = parse_plan_stub(fixture)
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], ".claude/tmp/1b-plan.md")
        self.assertEqual(result["feature"], "Add JWT refresh token rotation")
        self.assertEqual(result["plan_type"], "feat")
        self.assertEqual(result["waves"], 3)
        self.assertEqual(result["wave_sizes"], [4, 3, 2])
        self.assertEqual(result["total_tasks"], 9)
        self.assertEqual(result["models"]["haiku"], 7)
        self.assertEqual(result["models"]["sonnet"], 2)
        self.assertEqual(result["models"]["opus"], 0)
        self.assertEqual(result["stacks"], ["python", "react"])
        self.assertAlmostEqual(result["estimated_cost"], 0.18)
        self.assertEqual(result["deferred_items"], 2)

    def test_plan_stub_missing_returns_none(self) -> None:
        result = parse_plan_stub("Some random text without the marker")
        self.assertIsNone(result)

    def test_plan_stub_minimal(self) -> None:
        """A minimal stub should parse without optional fields."""
        output = "PLAN_WRITTEN: .claude/tmp/1b-plan.md\n\nSummary:\n- Total tasks: 3"
        result = parse_plan_stub(output)
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], ".claude/tmp/1b-plan.md")
        self.assertEqual(result["total_tasks"], 3)


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


class TestCostEstimateOutput(unittest.TestCase):
    def test_cost_estimate_parsing(self) -> None:
        fixture = (FIXTURES_DIR / "cost-estimate.txt").read_text()
        result = parse_cost_estimate_output(fixture)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "estimated")
        self.assertAlmostEqual(result["total_monthly"], 284.50)

    def test_cost_estimate_no_match(self) -> None:
        result = parse_cost_estimate_output("No cost data here")
        self.assertIsNone(result)


class TestSecurityScanOutput(unittest.TestCase):
    def test_security_scan_parsing(self) -> None:
        fixture = (FIXTURES_DIR / "security-scan-findings.txt").read_text()
        result = parse_security_scan_output(fixture)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "scanned")
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["critical"], 1)
        self.assertEqual(result["high"], 1)
        self.assertEqual(result["medium"], 2)
        self.assertEqual(result["low"], 0)

    def test_security_scan_no_match(self) -> None:
        result = parse_security_scan_output("No scan results")
        self.assertIsNone(result)


class TestDriftCheckOutput(unittest.TestCase):
    def test_drift_check_parsing(self) -> None:
        fixture = (FIXTURES_DIR / "drift-check-drifted.txt").read_text()
        result = parse_drift_check_output(fixture)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "checked")
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["drifted"], 2)
        self.assertEqual(result["compliant"], 2)
        self.assertEqual(result["missing"], 1)

    def test_drift_check_no_match(self) -> None:
        result = parse_drift_check_output("No drift data")
        self.assertIsNone(result)


class TestDeployBicepOutput(unittest.TestCase):
    def test_deploy_success_parsing(self) -> None:
        fixture = (FIXTURES_DIR / "deploy-success.txt").read_text()
        result = parse_deploy_bicep_output(fixture)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["modified"], 1)

    def test_deploy_failure_parsing(self) -> None:
        output = "DEPLOY FAILED | Resource group 'rg-staging' not found"
        result = parse_deploy_bicep_output(output)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("not found", result["error"])

    def test_deploy_no_match(self) -> None:
        result = parse_deploy_bicep_output("No deploy output")
        self.assertIsNone(result)


class TestAzureAuthOutput(unittest.TestCase):
    def test_auth_ok_parsing(self) -> None:
        fixture = (FIXTURES_DIR / "azure-auth-ok.txt").read_text()
        result = parse_azure_auth_output(fixture)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["subscription_name"], "My Dev Subscription")
        self.assertEqual(result["subscription_id"], "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        self.assertEqual(result["user"], "dev@contoso.com")
        self.assertEqual(result["method"], "interactive")

    def test_auth_failed_parsing(self) -> None:
        fixture = (FIXTURES_DIR / "azure-auth-failed.txt").read_text()
        result = parse_azure_auth_output(fixture)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("Not logged in", result["reason"])

    def test_auth_warning_parsing(self) -> None:
        output = "AZURE AUTH WARNING | Resource group 'rg-dev' does not exist"
        result = parse_azure_auth_output(output)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "warning")
        self.assertIn("does not exist", result["message"])

    def test_auth_no_match(self) -> None:
        result = parse_azure_auth_output("No auth output here")
        self.assertIsNone(result)


class TestPythonAdapterParseResults(unittest.TestCase):
    """Regression tests for parse_results() in adapters/python/scripts/test.py.

    Covers all pytest summary token orderings — critically including the
    default 'N failed, M passed' order that the old fixed-order regex missed.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        adapter_path = Path(__file__).resolve().parent.parent / "adapters/python/scripts/test.py"
        spec = importlib.util.spec_from_file_location("_python_test_adapter", adapter_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls._parse = staticmethod(mod.parse_results)

    def _run(self, summary_line: str):
        total, passed, failed, errors, _ = self._parse(summary_line)
        return total, passed, failed, errors

    def test_passed_only(self) -> None:
        total, passed, failed, errors = self._run("2 passed in 0.12s")
        self.assertEqual((total, passed, failed, errors), (2, 2, 0, 0))

    def test_failed_before_passed(self) -> None:
        """Pytest default order when failures exist: failed token precedes passed."""
        total, passed, failed, errors = self._run("17 failed, 520 passed in 2.00s")
        self.assertEqual((total, passed, failed, errors), (537, 520, 17, 0))

    def test_passed_before_failed(self) -> None:
        total, passed, failed, errors = self._run("520 passed, 17 failed in 2.00s")
        self.assertEqual((total, passed, failed, errors), (537, 520, 17, 0))

    def test_passed_failed_error(self) -> None:
        total, passed, failed, errors = self._run("1 passed, 1 failed, 1 error in 0.33s")
        self.assertEqual((total, passed, failed, errors), (3, 1, 1, 1))

    def test_passed_with_skipped(self) -> None:
        total, passed, failed, errors = self._run("5 passed, 2 skipped in 0.1s")
        self.assertEqual((total, passed, failed, errors), (5, 5, 0, 0))

    def test_failed_and_error_only(self) -> None:
        total, passed, failed, errors = self._run("3 failed, 1 error in 0.5s")
        self.assertEqual((total, passed, failed, errors), (4, 0, 3, 1))


class TestBicepAdapterBuildCommand(unittest.TestCase):
    """Regression tests for run_bicep_build() command construction.

    Issue #25: `az bicep build` requires `--file <path>` but the runner was
    passing the file positionally, which works for the standalone `bicep` CLI
    but fails under `az bicep build`.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        adapter_path = Path(__file__).resolve().parent.parent / "adapters/bicep/scripts/build.py"
        spec = importlib.util.spec_from_file_location("_bicep_build_adapter", adapter_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls._mod = mod

    def _capture(self, bicep_cmd):
        """Run run_bicep_build with subprocess.run stubbed; return the cmd list."""
        captured: list[list[str]] = []

        class _FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def _fake_run(cmd, **kwargs):
            captured.append(cmd)
            return _FakeResult()

        original = self._mod.subprocess.run
        self._mod.subprocess.run = _fake_run
        try:
            self._mod.run_bicep_build(".", ["main.bicep"], bicep_cmd)
        finally:
            self._mod.subprocess.run = original
        return captured[0]

    def test_az_driver_uses_file_flag(self) -> None:
        cmd = self._capture(["az", "bicep"])
        self.assertEqual(cmd, ["az", "bicep", "build", "--file", "main.bicep"])

    def test_standalone_driver_uses_positional(self) -> None:
        cmd = self._capture(["bicep"])
        self.assertEqual(cmd, ["bicep", "build", "main.bicep"])


class TestPythonAdapterInterpreter(unittest.TestCase):
    """Regression tests for _python_cmd() in adapters/python/scripts/test.py.

    Issue #32: bare `python3` was used for both pytest-cov detection and the
    pytest run, which fails for projects with project-local virtual environments
    (uv, poetry, plain venv) — system python3 cannot import the project's deps.
    The helper resolves to a venv interpreter when present, then to `uv run python`,
    then falls back to system `python3`.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        adapter_path = Path(__file__).resolve().parent.parent / "adapters/python/scripts/test.py"
        spec = importlib.util.spec_from_file_location("_python_test_adapter", adapter_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls._mod = mod

    def setUp(self) -> None:
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _make_venv(self, name: str) -> str:
        """Create a fake venv interpreter inside the tmp project. Returns its path."""
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        exe_name = "python.exe" if os.name == "nt" else "python"
        venv_bin = os.path.join(self._tmpdir, name, bin_dir)
        os.makedirs(venv_bin, exist_ok=True)
        path = os.path.join(venv_bin, exe_name)
        with open(path, "w") as f:
            f.write("#!/bin/sh\nexec /usr/bin/env python3 \"$@\"\n")
        os.chmod(path, 0o755)
        return path

    def test_dotvenv_takes_priority(self) -> None:
        venv_python = self._make_venv(".venv")
        # Even with a `venv/` and uv available, .venv wins.
        self._make_venv("venv")
        with open(os.path.join(self._tmpdir, "pyproject.toml"), "w"):
            pass
        cmd = self._mod._python_cmd(self._tmpdir)
        self.assertEqual(cmd, [venv_python])

    def test_venv_used_when_dotvenv_absent(self) -> None:
        venv_python = self._make_venv("venv")
        cmd = self._mod._python_cmd(self._tmpdir)
        self.assertEqual(cmd, [venv_python])

    def test_uv_run_when_pyproject_present_no_venv(self) -> None:
        with open(os.path.join(self._tmpdir, "pyproject.toml"), "w"):
            pass
        # Stub shutil.which inside the adapter module to simulate uv on PATH.
        original_which = self._mod.shutil.which
        self._mod.shutil.which = lambda name: "/fake/uv" if name == "uv" else None
        try:
            cmd = self._mod._python_cmd(self._tmpdir)
            self.assertEqual(cmd, ["uv", "run", "python"])
        finally:
            self._mod.shutil.which = original_which

    def test_falls_back_to_python3(self) -> None:
        # No venvs, no pyproject — fallback path. Stub uv away to ensure determinism.
        original_which = self._mod.shutil.which
        self._mod.shutil.which = lambda name: None
        try:
            cmd = self._mod._python_cmd(self._tmpdir)
            self.assertEqual(cmd, ["python3"])
        finally:
            self._mod.shutil.which = original_which


class TestReactAdapterParsers(unittest.TestCase):
    """Regression tests for parsers in adapters/react/scripts/test.py.

    Covers the vitest/jest JSON parsers, the text-summary fallback, and the
    JSON-load diagnostic capture. Issue #26: the test runner swallowed green
    vitest runs because --reporter=json suppresses the text summary, the
    JSON file occasionally fails to parse, and the fallback regex required a
    fixed token order.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        adapter_path = Path(__file__).resolve().parent.parent / "adapters/react/scripts/test.py"
        spec = importlib.util.spec_from_file_location("_react_test_adapter", adapter_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls._mod = mod

    def test_vitest_json_mixed_results(self) -> None:
        fixture = str(FIXTURES_DIR / "vitest-results.json")
        result = self._mod.parse_vitest_json(fixture, "")
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["failed"], 2)
        self.assertEqual(len(result["failures"]), 2)
        self.assertIn("CoinTile", result["failures"][0]["test"])

    def test_jest_json_uses_top_level_counts(self) -> None:
        # Jest & vitest share the same JSON shape; parse_jest_json relies on
        # the numTotalTests/numPassedTests/numFailedTests top-level keys.
        fixture = str(FIXTURES_DIR / "vitest-results.json")
        result = self._mod.parse_jest_json(fixture, "")
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["failed"], 2)

    def test_fallback_vitest_success(self) -> None:
        fixture = (FIXTURES_DIR / "vitest-text-success.txt").read_text()
        result = self._mod.parse_fallback(fixture)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["passed"], 5)
        self.assertEqual(result["failed"], 0)

    def test_fallback_vitest_mixed_order_independent(self) -> None:
        fixture = (FIXTURES_DIR / "vitest-text-mixed.txt").read_text()
        result = self._mod.parse_fallback(fixture)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["failed"], 2)

    def test_fallback_vitest_passed_before_failed(self) -> None:
        # Reversed token order — old regex dropped 'failed' when it came
        # after 'passed'. Token-based parse must handle either order.
        text = """ Test Files  1 failed | 1 passed (2)
      Tests  3 passed | 2 failed (5)
"""
        result = self._mod.parse_fallback(text)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["failed"], 2)

    def test_fallback_jest_failed_before_passed(self) -> None:
        fixture = (FIXTURES_DIR / "jest-text-mixed.txt").read_text()
        result = self._mod.parse_fallback(fixture)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["failed"], 2)

    def test_load_json_empty_file_records_diagnostic(self) -> None:
        import tempfile, os as _os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            empty_path = f.name
        try:
            diagnostics: list[str] = []
            result = self._mod._load_json_results(empty_path, "", diagnostics)
            self.assertIsNone(result)
            self.assertEqual(len(diagnostics), 1)
            self.assertIn("empty", diagnostics[0].lower())
        finally:
            _os.remove(empty_path)

    def test_load_json_malformed_records_diagnostic(self) -> None:
        import tempfile, os as _os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{ not valid json")
            bad_path = f.name
        try:
            diagnostics: list[str] = []
            result = self._mod._load_json_results(bad_path, "", diagnostics)
            self.assertIsNone(result)
            self.assertEqual(len(diagnostics), 1)
            self.assertIn("malformed", diagnostics[0].lower())
        finally:
            _os.remove(bad_path)


if __name__ == "__main__":
    unittest.main()
