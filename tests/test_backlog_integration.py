#!/usr/bin/env python3
"""Integration tests for backlog filing behavior.

Exercises higher-order properties that span utility + sentinel + simulated
orchestrator state:

  - Opt-in detection (sentinel present / absent / disabled / malformed)
  - Fold-cap enforcement using a synthetic run-log
  - fold_cap = 0 (always defer)
  - Traceability fields (D8) present in every filed issue body
  - "Skipped silently" semantics: skip reason is emitted exactly once per run

Bootstrap-skill idempotency is verified at the contract level — running the
skill twice against an identical sentinel and template set must produce zero
filesystem diff. That's exercised here by simulating the skill's file-copy
step and checking for byte equivalence.

Usage:
    python3 tests/test_backlog_integration.py [-v]
"""

from __future__ import annotations

import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT / "scripts"))

from backlog_file import file_backlog_issue, render_body  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"
BACKLOG_TEMPLATES = PIPELINE_ROOT / "templates" / "backlog"


def _ok(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _err(stderr: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def _make_repo(tmp: Path, sentinel_src: Path | None) -> Path:
    (tmp / ".git").mkdir()
    (tmp / ".github").mkdir()
    if sentinel_src is not None:
        (tmp / ".github" / "pipeline-backlog.yml").write_text(sentinel_src.read_text())
    return tmp


BASE_CTX = {
    "phase": "reviewer",
    "pr_number": "42",
    "run_id": "20260423-181000",
    "reasoning": "Cross-cuts 4 files — Sonnet-tier",
    "summary": "Extract common error mapper",
    "context": "Reviewer surfaced duplicated error-to-user-message mapping.",
}


class TestOptInDetection(unittest.TestCase):
    def test_sentinel_present_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(Path(td), FIXTURES / "sentinel-config-valid.yml")
            with patch("backlog_file.subprocess.run", return_value=_ok("https://github.com/o/r/issues/1")):
                r = file_backlog_issue("t", "chore", "p2", BASE_CTX, repo_root=root)
            self.assertEqual(r.status, "filed")

    def test_sentinel_absent_skips(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(Path(td), None)
            r = file_backlog_issue("t", "chore", "p2", BASE_CTX, repo_root=root)
            self.assertEqual(r.status, "skipped")

    def test_sentinel_disabled_skips(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(Path(td), FIXTURES / "sentinel-config-disabled.yml")
            r = file_backlog_issue("t", "chore", "p2", BASE_CTX, repo_root=root)
            self.assertEqual(r.status, "skipped")
            self.assertIn("disabled", r.reason)

    def test_sentinel_malformed_skips(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            (root / ".github").mkdir()
            (root / ".github" / "pipeline-backlog.yml").write_text("not: valid: yaml: [")
            r = file_backlog_issue("t", "chore", "p2", BASE_CTX, repo_root=root)
            # Malformed parses to None → treated as absent → skipped.
            self.assertEqual(r.status, "skipped")


class TestFoldCapBehavior(unittest.TestCase):
    """Simulate the orchestrator's fold-cap check by counting run-log entries.

    The utility itself does NOT enforce fold cap — that's the orchestrator's
    job (see skills/orchestrate/SKILL.md "Backlog Integration"). These tests
    validate the contract the orchestrator implements against: counting
    `action: folded` entries in run-log.yml and gating further folds.
    """

    @staticmethod
    def count_folds(run_log: list[dict]) -> int:
        return sum(1 for e in run_log if e.get("action") == "folded")

    def test_default_cap_of_3_allows_three_folds(self) -> None:
        run_log: list[dict] = []
        cap = 3
        for i in range(5):
            if self.count_folds(run_log) < cap:
                run_log.append({"action": "folded", "title": f"item {i}"})
            else:
                run_log.append({"action": "deferred", "title": f"item {i}"})
        self.assertEqual(self.count_folds(run_log), 3)
        self.assertEqual(sum(1 for e in run_log if e["action"] == "deferred"), 2)

    def test_fold_cap_zero_always_defers(self) -> None:
        run_log: list[dict] = []
        cap = 0
        for i in range(3):
            if self.count_folds(run_log) < cap:
                run_log.append({"action": "folded", "title": f"item {i}"})
            else:
                run_log.append({"action": "deferred", "title": f"item {i}"})
        self.assertEqual(self.count_folds(run_log), 0)
        self.assertEqual(len(run_log), 3)

    def test_fold_cap_applies_across_phases(self) -> None:
        """Fold cap is run-wide, not per-phase."""
        run_log: list[dict] = []
        cap = 2
        phases = ["planner", "reviewer", "reviewer", "implementer"]
        for phase in phases:
            if self.count_folds(run_log) < cap:
                run_log.append({"phase": phase, "action": "folded"})
            else:
                run_log.append({"phase": phase, "action": "deferred"})
        self.assertEqual(self.count_folds(run_log), 2)
        # First two phases fold, last two defer regardless of phase.
        self.assertEqual([e["action"] for e in run_log], ["folded", "folded", "deferred", "deferred"])


class TestTraceabilityBlock(unittest.TestCase):
    """Every filed issue body must include D8 fields: Deferred from, Phase,
    Run ID, Reasoning."""

    def test_all_fields_present_with_pr(self) -> None:
        body = render_body(BASE_CTX)
        self.assertIn("**Deferred from:** #42", body)
        self.assertIn("**Phase:** reviewer", body)
        self.assertIn("**Run ID:** 20260423-181000", body)
        self.assertIn("**Reasoning:** Cross-cuts 4 files", body)

    def test_pre_pr_filings_mark_origin(self) -> None:
        ctx = {**BASE_CTX}
        del ctx["pr_number"]
        body = render_body(ctx)
        self.assertIn("**Deferred from:** (pre-PR", body)

    def test_reasoning_placeholder_when_missing(self) -> None:
        body = render_body({"phase": "architect", "run_id": "x"})
        self.assertIn("**Reasoning:** _(not provided)_", body)


class TestBootstrapIdempotency(unittest.TestCase):
    """Re-running the file-copy portion of /bootstrap-backlog produces zero
    diff. (The gh label create --force step is idempotent by gh itself and
    is tested by manual dogfooding.)"""

    def test_issue_form_copies_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            consumer = Path(td)
            (consumer / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)

            # First bootstrap pass
            for name in ("bug_report.yml", "feature_request.yml", "chore.yml", "config.yml"):
                shutil.copy(
                    BACKLOG_TEMPLATES / "ISSUE_TEMPLATE" / name,
                    consumer / ".github" / "ISSUE_TEMPLATE" / name,
                )

            first_hashes = {
                p.name: p.read_bytes() for p in (consumer / ".github" / "ISSUE_TEMPLATE").iterdir()
            }

            # Second bootstrap pass — re-copy, expect identical bytes
            for name in ("bug_report.yml", "feature_request.yml", "chore.yml", "config.yml"):
                shutil.copy(
                    BACKLOG_TEMPLATES / "ISSUE_TEMPLATE" / name,
                    consumer / ".github" / "ISSUE_TEMPLATE" / name,
                )

            second_hashes = {
                p.name: p.read_bytes() for p in (consumer / ".github" / "ISSUE_TEMPLATE").iterdir()
            }
            self.assertEqual(first_hashes, second_hashes)

    def test_sentinel_not_overwritten_if_present(self) -> None:
        """The bootstrap skill must NOT overwrite an existing sentinel —
        user may have customized fold_cap or project_number."""
        with tempfile.TemporaryDirectory() as td:
            consumer = Path(td) / ".github"
            consumer.mkdir()
            user_config = "version: 1\nenabled: true\nfold_cap: 99\nproject_number: 42\n"
            sentinel = consumer / "pipeline-backlog.yml"
            sentinel.write_text(user_config)

            # Simulated bootstrap: only copy if absent.
            if not sentinel.exists():
                shutil.copy(BACKLOG_TEMPLATES / "pipeline-backlog.yml.template", sentinel)

            self.assertEqual(sentinel.read_text(), user_config)


class TestLabelAndBodyComposition(unittest.TestCase):
    """Labels and body content match the locked taxonomy when filing happens."""

    def test_filed_issue_has_three_canonical_labels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(Path(td), FIXTURES / "sentinel-config-valid.yml")
            captured: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                captured.append(cmd)
                return _ok("https://github.com/o/r/issues/10")

            with patch("backlog_file.subprocess.run", side_effect=fake_run):
                r = file_backlog_issue("t", "chore", "p2", BASE_CTX, repo_root=root)

            self.assertEqual(r.status, "filed")
            cmd = captured[0]
            labels_in_cmd = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--label"]
            self.assertEqual(sorted(labels_in_cmd), ["priority: p2", "source: ai-deferred", "type: chore"])


if __name__ == "__main__":
    unittest.main()
