#!/usr/bin/env python3
"""Run a pipeline benchmark and produce metrics.json.

Three pipeline-invocation modes:
  --mode=auto      Invoke `claude -p` headlessly. Costs API tokens. Requires claude CLI.
  --mode=manual    Print instructions, wait for the user to run /orchestrate, then continue.
  --mode=existing  Skip pipeline run entirely; score whatever is already in --project-dir.

Usage:
    python3 benchmarks/scripts/run_benchmark.py tier1-base64 --mode=manual
    python3 benchmarks/scripts/run_benchmark.py tier1-base64 --mode=existing --project-dir=/tmp/already-built
    python3 benchmarks/scripts/run_benchmark.py tier1-base64 --mode=auto --runs=3
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARKS_DIR = PIPELINE_ROOT / "benchmarks"
RUNS_DIR = BENCHMARKS_DIR / "runs"

sys.path.insert(0, str(BENCHMARKS_DIR / "scripts"))
from capture_metrics import capture  # noqa: E402
from score_run import score  # noqa: E402


def _now_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PIPELINE_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return out or "unknown"
    except subprocess.CalledProcessError:
        return "unknown"


def setup_skeleton(benchmark: str, work_root: Path) -> Path:
    """Copy skeleton into work_root, git-init, run init.sh. Return project dir."""
    skeleton_src = BENCHMARKS_DIR / benchmark / "skeleton"
    if not skeleton_src.is_dir():
        raise FileNotFoundError(f"Skeleton missing: {skeleton_src}")

    project_dir = work_root / "project"
    shutil.copytree(skeleton_src, project_dir)

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "benchmark",
        "GIT_AUTHOR_EMAIL": "benchmark@local",
        "GIT_COMMITTER_NAME": "benchmark",
        "GIT_COMMITTER_EMAIL": "benchmark@local",
    }
    subprocess.run(["git", "init", "-q"], cwd=project_dir, check=True, env=env)
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "skeleton baseline"],
                   cwd=project_dir, check=True, env=env)

    init_sh = PIPELINE_ROOT / "init.sh"
    proc = subprocess.run(
        ["bash", str(init_sh), str(project_dir), "--stack=python"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"init.sh failed: {proc.stderr}")

    # Re-commit so post-bootstrap state is the diff baseline for code-delta metrics.
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "post-bootstrap"],
                   cwd=project_dir, check=True, env=env, capture_output=True)
    return project_dir


def invoke_pipeline_auto(project_dir: Path, feature_request: str, log_path: Path) -> int:
    """Run claude -p headlessly. Returns wall seconds."""
    cli = shutil.which("claude")
    if cli is None:
        raise RuntimeError("`claude` CLI not on PATH; use --mode=manual or set --cli-cmd")
    prompt = f"/orchestrate\n\n{feature_request}"
    started = time.time()
    with log_path.open("w") as logf:
        proc = subprocess.run(
            [cli, "-p", prompt],
            cwd=project_dir,
            stdout=logf, stderr=subprocess.STDOUT,
            text=True,
        )
    elapsed = int(time.time() - started)
    if proc.returncode != 0:
        print(f"WARNING: claude exited {proc.returncode}; metrics may be partial")
    return elapsed


def invoke_pipeline_manual(project_dir: Path, log_path: Path) -> int:
    """Print instructions, wait for user keypress."""
    print()
    print("=" * 60)
    print("MANUAL MODE")
    print("=" * 60)
    print(f"  1. cd {project_dir}")
    print(f"  2. Open Claude Code there and run:")
    print(f"     /orchestrate {BENCHMARKS_DIR.relative_to(PIPELINE_ROOT)}/<benchmark>/feature-request.md")
    print(f"     (paste the contents of feature-request.md as the request)")
    print(f"  3. Save the session transcript to: {log_path}")
    print(f"     (or leave empty — metrics will be partial without it)")
    print("=" * 60)
    started = time.time()
    input("Press ENTER when /orchestrate has finished... ")
    elapsed = int(time.time() - started)
    if not log_path.exists():
        log_path.write_text("")  # empty placeholder
    return elapsed


def run_tests(project_dir: Path, fixtures_dir: Path, run_dir: Path) -> dict[str, Any]:
    prop_json = run_dir / "property_results.json"
    unit_json = run_dir / "unit_results.json"

    prop_proc = subprocess.run(
        [sys.executable, str(fixtures_dir / "property_tests.py"),
         "--project", str(project_dir),
         "--json", str(prop_json),
         "--runs", "1000"],
        capture_output=True, text=True, timeout=120,
    )
    print(prop_proc.stdout)
    if prop_proc.returncode == 2:
        print(f"  Property suite: discovery failed (exit 2)")

    unit_proc = subprocess.run(
        [sys.executable, str(fixtures_dir / "unit_tests.py"),
         "--project", str(project_dir),
         "--json", str(unit_json)],
        capture_output=True, text=True, timeout=60,
    )
    print(unit_proc.stdout)

    prop = json.loads(prop_json.read_text()) if prop_json.exists() else {"error": "missing"}
    unit = json.loads(unit_json.read_text()) if unit_json.exists() else {"error": "missing"}
    return {"property": prop, "unit": unit}


def collect_code_delta(project_dir: Path) -> dict[str, int]:
    """Diff against the post-bootstrap commit to count code added by the pipeline.

    Tolerant of non-git project dirs (e.g. --mode=existing on a plain dir).
    """
    is_git = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_dir, capture_output=True, text=True,
    ).returncode == 0
    if not is_git:
        return {"files_changed": 0, "lines_added": 0, "lines_deleted": 0}

    try:
        out = subprocess.check_output(
            ["git", "diff", "--shortstat", "HEAD"],
            cwd=project_dir, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return {"files_changed": 0, "lines_added": 0, "lines_deleted": 0}

    # Format: " 3 files changed, 187 insertions(+), 4 deletions(-)"
    files, added, deleted = 0, 0, 0
    for token in out.replace(",", "").split():
        if token.isdigit():
            n = int(token)
            if "file" in out[out.index(token):out.index(token)+10]:
                files = files or n
            elif "insertion" in out[out.index(token):out.index(token)+15]:
                added = added or n
            elif "deletion" in out[out.index(token):out.index(token)+15]:
                deleted = deleted or n

    # Also count untracked files (pipeline may not have committed)
    try:
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=project_dir, text=True,
        ).strip().splitlines()
        for u in untracked:
            files += 1
            try:
                added += sum(1 for _ in (project_dir / u).read_text().splitlines())
            except (OSError, UnicodeDecodeError):
                pass
    except subprocess.CalledProcessError:
        pass

    return {"files_changed": files, "lines_added": added, "lines_deleted": deleted}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("benchmark", help="Benchmark name (e.g. tier1-base64)")
    p.add_argument("--mode", choices=["auto", "manual", "existing"], default="manual")
    p.add_argument("--project-dir", default=None,
                   help="(--mode=existing) project dir to score; otherwise a temp dir is used")
    p.add_argument("--runs-dir", default=None,
                   help="Override runs/ output directory (default: benchmarks/runs/)")
    p.add_argument("--keep-workdir", action="store_true",
                   help="Don't delete the work dir at the end")
    p.add_argument("--log-path", default=None,
                   help="Path to capture (auto) or read (manual) the pipeline log")
    args = p.parse_args()

    benchmark_dir = BENCHMARKS_DIR / args.benchmark
    if not benchmark_dir.is_dir():
        print(f"ERROR: benchmark not found: {benchmark_dir}")
        return 1

    runs_dir = Path(args.runs_dir) if args.runs_dir else RUNS_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{_now_id()}-{_git_sha()}-{args.benchmark}"
    run_dir = runs_dir / run_id
    run_dir.mkdir()

    log_path = Path(args.log_path) if args.log_path else (run_dir / "pipeline.log")

    # 1. Setup project dir
    if args.mode == "existing":
        if not args.project_dir:
            print("ERROR: --mode=existing requires --project-dir")
            return 1
        project_dir = Path(args.project_dir)
        if not project_dir.is_dir():
            print(f"ERROR: --project-dir does not exist: {project_dir}")
            return 1
        work_root = None
        wall_seconds = 0
    else:
        work_root = Path(tempfile.mkdtemp(prefix=f"bench-{args.benchmark}-"))
        print(f"Work dir: {work_root}")
        project_dir = setup_skeleton(args.benchmark, work_root)

        # 2. Run pipeline
        if args.mode == "auto":
            wall_seconds = invoke_pipeline_auto(
                project_dir, (benchmark_dir / "feature-request.md").read_text(), log_path
            )
        else:  # manual
            wall_seconds = invoke_pipeline_manual(project_dir, log_path)

    # 3. Run tests
    print()
    print("Running tests against produced code...")
    test_results = run_tests(project_dir, benchmark_dir / "fixtures", run_dir)

    # 4. Code delta
    code_delta = collect_code_delta(project_dir)

    # 5. Capture pipeline metrics from log
    pipeline_metrics = capture(log_path) if log_path.exists() else {
        "tokens": {}, "pipeline": {}, "log_present": False,
    }

    # 6. Compose + score
    metrics = {
        "run_id": run_id,
        "benchmark": args.benchmark,
        "pipeline_sha": _git_sha(),
        "mode": args.mode,
        "wall_time_seconds": wall_seconds,
        "tokens": pipeline_metrics.get("tokens", {}),
        "pipeline": pipeline_metrics.get("pipeline", {}),
        "code_delta": code_delta,
        "tests": test_results,
    }
    metrics["score"] = score(metrics)

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print()
    print(f"Metrics written: {metrics_path}")
    print(f"  Correctness: {metrics['score']['correctness']:.3f}")
    print(f"  Composite:   {metrics['score']['composite']:.3f}")

    # 7. Cleanup work dir
    if work_root and not args.keep_workdir:
        # Save artifacts dir under run before nuking
        artifacts = run_dir / "artifacts"
        if not artifacts.exists():
            shutil.copytree(project_dir, artifacts, ignore=shutil.ignore_patterns(".git", ".claude"))
        shutil.rmtree(work_root, ignore_errors=True)
    elif work_root:
        print(f"Kept work dir: {work_root}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
