#!/usr/bin/env python3
"""Unit tests for scripts/backlog_file.py.

Mocks `gh` subprocess calls and exercises every branch of file_backlog_issue:
opt-in detection, input validation, body rendering, label construction, gh
failure fallback, and project item-add.

Usage:
    python3 tests/test_backlog_utility.py [-v]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT / "scripts"))

from backlog_file import (  # noqa: E402
    IssueResult,
    file_backlog_issue,
    find_repo_root,
    read_sentinel,
    render_body,
    _parse_minimal_yaml,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _make_opted_in_repo(tmp: Path, sentinel_src: str = "sentinel-config-valid.yml") -> Path:
    """Create a temp git repo with a sentinel, return repo_root."""
    (tmp / ".git").mkdir()
    (tmp / ".github").mkdir()
    (tmp / ".github" / "pipeline-backlog.yml").write_text(
        (FIXTURES_DIR / sentinel_src).read_text()
    )
    return tmp


def _make_bare_repo(tmp: Path) -> Path:
    """Create a temp git repo WITHOUT a sentinel."""
    (tmp / ".git").mkdir()
    return tmp


def _ok(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _err(stderr: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


class TestFindRepoRoot(unittest.TestCase):
    def test_walks_up_to_git_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            nested = root / "a" / "b" / "c"
            nested.mkdir(parents=True)
            self.assertEqual(find_repo_root(nested), root.resolve())

    def test_returns_none_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(find_repo_root(Path(td)))


class TestReadSentinel(unittest.TestCase):
    def test_absent_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(read_sentinel(Path(td)))

    def test_valid_returns_dict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_opted_in_repo(Path(td))
            parsed = read_sentinel(root)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["version"], 1)
            self.assertIs(parsed["enabled"], True)
            self.assertEqual(parsed["fold_cap"], 3)
            self.assertIsNone(parsed["project_number"])


class TestMinimalYAMLParser(unittest.TestCase):
    def test_bool_int_null_and_string(self) -> None:
        text = (
            "version: 1\n"
            "enabled: true\n"
            "fold_cap: 0\n"
            "project_number: null\n"
            'name: "pipeline"\n'
        )
        parsed = _parse_minimal_yaml(text)
        self.assertEqual(parsed["version"], 1)
        self.assertIs(parsed["enabled"], True)
        self.assertEqual(parsed["fold_cap"], 0)
        self.assertIsNone(parsed["project_number"])
        self.assertEqual(parsed["name"], "pipeline")

    def test_comments_ignored(self) -> None:
        parsed = _parse_minimal_yaml("# comment\nversion: 1  # inline\n")
        self.assertEqual(parsed, {"version": 1})


class TestRenderBody(unittest.TestCase):
    def test_full_body_matches_expected(self) -> None:
        body = render_body({
            "phase": "reviewer",
            "pr_number": "42",
            "run_id": "20260423-181000",
            "reasoning": "Cross-cuts 4 files, adds new abstraction — Sonnet-tier.",
            "summary": "Extract common error mapper for Grok client",
            "context": (
                "Reviewer surfaced duplicated error-to-user-message mapping in 4 "
                "files during\nwave 2. A single mapper keeps the UX consistent "
                "when the API changes."
            ),
            "acceptance": (
                "A `GrokErrorMapper` class under `src/tools/grok_client.py` with "
                "unit tests; callers refactored to use it."
            ),
        })
        expected = (FIXTURES_DIR / "backlog-issue-body-expected.md").read_text()
        self.assertEqual(body, expected)

    def test_missing_pr_number_uses_pre_pr_placeholder(self) -> None:
        body = render_body({"phase": "architect", "run_id": "x", "reasoning": "r"})
        self.assertIn("**Deferred from:** (pre-PR", body)

    def test_all_d8_fields_present(self) -> None:
        body = render_body({
            "phase": "token-analysis",
            "pr_number": "99",
            "run_id": "20260423",
            "reasoning": "Because reasons",
            "summary": "s",
            "context": "c",
        })
        for fragment in ("**Deferred from:**", "**Phase:**", "**Run ID:**", "**Reasoning:**"):
            self.assertIn(fragment, body)


class TestFileBacklogIssue(unittest.TestCase):
    BASE_CTX = {
        "phase": "reviewer",
        "pr_number": "42",
        "run_id": "20260423-181000",
        "reasoning": "r",
        "summary": "s",
        "context": "c",
    }

    def test_invalid_type_returns_failed(self) -> None:
        r = file_backlog_issue(title="x", type="BOGUS", priority="p2", body_context=self.BASE_CTX)
        self.assertEqual(r.status, "failed")
        self.assertIn("invalid type", r.reason)

    def test_invalid_priority_returns_failed(self) -> None:
        r = file_backlog_issue(title="x", type="chore", priority="p9", body_context=self.BASE_CTX)
        self.assertEqual(r.status, "failed")
        self.assertIn("invalid priority", r.reason)

    def test_missing_sentinel_returns_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_bare_repo(Path(td))
            r = file_backlog_issue(
                title="x", type="chore", priority="p2",
                body_context=self.BASE_CTX, repo_root=root,
            )
            self.assertEqual(r.status, "skipped")
            self.assertIn("not enabled", r.reason)

    def test_disabled_sentinel_returns_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_opted_in_repo(Path(td), sentinel_src="sentinel-config-disabled.yml")
            r = file_backlog_issue(
                title="x", type="chore", priority="p2",
                body_context=self.BASE_CTX, repo_root=root,
            )
            self.assertEqual(r.status, "skipped")
            self.assertIn("disabled", r.reason)

    def test_filed_happy_path_builds_correct_labels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_opted_in_repo(Path(td))
            with patch("backlog_file.subprocess.run", return_value=_ok("https://github.com/o/r/issues/77")) as m:
                r = file_backlog_issue(
                    title="t", type="chore", priority="p2",
                    body_context=self.BASE_CTX, repo_root=root,
                )
            self.assertEqual(r.status, "filed")
            self.assertEqual(r.number, 77)
            self.assertEqual(r.url, "https://github.com/o/r/issues/77")
            cmd = m.call_args.args[0]
            self.assertIn("type: chore", cmd)
            self.assertIn("priority: p2", cmd)
            self.assertIn("source: ai-deferred", cmd)

    def test_failed_gh_retries_without_source_label(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_opted_in_repo(Path(td))
            calls = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)
                if "source: ai-deferred" in cmd:
                    return _err("label not found")
                return _ok("https://github.com/o/r/issues/88")

            with patch("backlog_file.subprocess.run", side_effect=fake_run):
                r = file_backlog_issue(
                    title="t", type="chore", priority="p2",
                    body_context=self.BASE_CTX, repo_root=root,
                )
            self.assertEqual(r.status, "filed")
            self.assertEqual(r.number, 88)
            self.assertEqual(len(calls), 2)

    def test_persistent_gh_failure_returns_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = _make_opted_in_repo(Path(td))
            with patch("backlog_file.subprocess.run", return_value=_err("network down")):
                r = file_backlog_issue(
                    title="t", type="chore", priority="p2",
                    body_context=self.BASE_CTX, repo_root=root,
                )
            self.assertEqual(r.status, "failed")
            self.assertIn("network down", r.reason)

    def test_project_item_add_called_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            (root / ".github").mkdir()
            (root / ".github" / "pipeline-backlog.yml").write_text(
                "version: 1\nenabled: true\nfold_cap: 3\nproject_number: 7\n"
            )
            calls = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)
                if cmd[:3] == ["gh", "issue", "create"]:
                    return _ok("https://github.com/o/r/issues/5")
                return _ok("added")

            with patch("backlog_file.subprocess.run", side_effect=fake_run):
                r = file_backlog_issue(
                    title="t", type="chore", priority="p2",
                    body_context=self.BASE_CTX, repo_root=root,
                )
            self.assertEqual(r.status, "filed")
            self.assertTrue(any(cmd[:3] == ["gh", "project", "item-add"] for cmd in calls))


if __name__ == "__main__":
    unittest.main()
