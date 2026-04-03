#!/usr/bin/env python3
"""
Run Flutter tests and output a minimal results table.

Usage examples:
  # Auto-detect everything
  python test.py --project-dir .

  # Without coverage
  python test.py --project-dir . --no-coverage

  # Exclude patterns from coverage
  python test.py --project-dir . --exclude-from-coverage '*.g.dart' '*.freezed.dart'

  # Run specific test directory
  python test.py --project-dir . --test-dir test/unit
"""

import subprocess
import sys
import re
import argparse
import os
import json
import fnmatch


# ---------------------------------------------------------------------------
# Flutter SDK detection
# ---------------------------------------------------------------------------

def find_flutter():
    """Find the flutter executable."""
    for cmd in ["flutter", "fvm flutter"]:
        try:
            result = subprocess.run(
                cmd.split() + ["--version"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return cmd.split()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    fvm_path = os.path.join(".fvm", "flutter_sdk", "bin", "flutter")
    if os.path.exists(fvm_path):
        return [fvm_path]

    print("ERROR: Flutter SDK not found. Ensure 'flutter' is in PATH or FVM is configured.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def run_tests(project_dir, flutter_cmd, coverage=True, test_dir=None):
    """
    Run flutter test and return (stdout+stderr, returncode).
    Uses --machine for JSON output on stdout.
    """
    cmd = flutter_cmd + ["test", "--machine", "--no-pub"]

    if coverage:
        cmd.append("--coverage")

    if test_dir:
        cmd.append(test_dir)

    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return result.stdout, result.stderr, result.returncode


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

def parse_machine_output(stdout):
    """
    Parse flutter test --machine JSON output.
    Each line is a separate JSON event.
    Returns (total, passed, failed, skipped, failures).
    """
    tests = {}  # id -> test info
    results = {}  # id -> result
    failures = []

    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")

        if event_type == "testStart":
            test_info = event.get("test", {})
            test_id = test_info.get("id")
            if test_id is not None:
                tests[test_id] = test_info

        elif event_type == "testDone":
            test_id = event.get("testID")
            if test_id is not None:
                results[test_id] = {
                    "hidden": event.get("hidden", False),
                    "skipped": event.get("skipped", False),
                    "result": event.get("result", ""),
                }

        elif event_type == "error":
            test_id = event.get("testID")
            error_msg = event.get("error", "Unknown error")
            # Clean up error message
            error_msg = error_msg.split("\n")[0].strip()[:160]
            if test_id is not None and test_id in tests:
                test_info = tests[test_id]
                suite_path = test_info.get("root_url", test_info.get("url", ""))
                if suite_path:
                    suite_path = _shorten_path(suite_path)
                failures.append({
                    "suite": suite_path or "unknown",
                    "test": test_info.get("name", "unknown"),
                    "msg": error_msg,
                })

    # Count results (exclude hidden/setup tests)
    total = 0
    passed = 0
    failed = 0
    skipped = 0

    for test_id, result in results.items():
        if result.get("hidden"):
            continue
        total += 1
        if result.get("skipped"):
            skipped += 1
        elif result.get("result") == "success":
            passed += 1
        elif result.get("result") == "error" or result.get("result") == "failure":
            failed += 1

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def parse_fallback(stderr):
    """
    Fallback parser when --machine output is unavailable or empty.
    Parses text output for pass/fail counts.
    """
    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures = []

    # Flutter test summary line: XX:XX +N -M: Some message
    # Or: XX:XX +N: All tests passed!
    summary_pattern = re.compile(
        r"(\d+:\d+)\s+\+(\d+)(?:\s+~(\d+))?(?:\s+-(\d+))?:\s+(.*)"
    )

    # Find the last summary line
    last_match = None
    for m in summary_pattern.finditer(stderr):
        last_match = m

    if last_match:
        passed = int(last_match.group(2))
        skipped = int(last_match.group(3) or 0)
        failed = int(last_match.group(4) or 0)
        total = passed + failed + skipped

    # Extract failure details
    fail_pattern = re.compile(
        r"^(.*\.dart)\s+.*?(?:FAILED|ERROR)\s*$", re.MULTILINE
    )
    for m in fail_pattern.finditer(stderr):
        filepath = _shorten_path(m.group(1).strip())
        failures.append({
            "suite": filepath,
            "test": "See output above",
            "msg": "",
        })

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Coverage parsing
# ---------------------------------------------------------------------------

def parse_coverage(project_dir, exclude_patterns=None):
    """
    Parse coverage from lcov.info file produced by flutter test --coverage.
    Returns dict with 'overall' (float %), 'per_target' (list of strings), or None.
    """
    lcov_path = os.path.join(project_dir, "coverage", "lcov.info")
    if not os.path.exists(lcov_path):
        return None

    try:
        with open(lcov_path) as f:
            content = f.read()
    except IOError:
        return None

    # Parse LCOV format
    total_lines = 0
    covered_lines = 0
    excluded_lines = 0
    excluded_covered = 0
    per_file = []  # (short_path, pct, file_total)
    current_file = None
    file_total = 0
    file_covered = 0

    for line in content.splitlines():
        if line.startswith("SF:"):
            current_file = line[3:].strip()
            file_total = 0
            file_covered = 0
        elif line.startswith("LF:"):
            file_total = int(line[3:].strip())
        elif line.startswith("LH:"):
            file_covered = int(line[3:].strip())
        elif line.startswith("end_of_record"):
            if current_file and file_total > 0:
                short = _shorten_path(current_file)

                if exclude_patterns and _file_matches_patterns(current_file, exclude_patterns):
                    excluded_lines += file_total
                    excluded_covered += file_covered
                else:
                    total_lines += file_total
                    covered_lines += file_covered
                    pct = file_covered / file_total * 100
                    per_file.append((short, pct, file_total))

            current_file = None

    if total_lines == 0:
        return None

    overall = covered_lines / total_lines * 100
    per_target = _group_by_directory(per_file)

    result = {"overall": overall, "per_target": per_target}
    if exclude_patterns and excluded_lines > 0:
        result["excluded_lines"] = excluded_lines
        result["excluded_pct"] = excluded_covered / excluded_lines * 100
    return result


def _group_by_directory(per_file):
    """Group per-file coverage into per-directory summaries."""
    dir_stats = {}
    for short_path, pct, file_total in per_file:
        parts = short_path.split("/")
        if len(parts) >= 2:
            dir_key = parts[0] if parts[0] != "lib" else (parts[1] if len(parts) > 2 else "lib")
        else:
            dir_key = "root"
        if dir_key not in dir_stats:
            dir_stats[dir_key] = [0, 0]
        dir_stats[dir_key][0] += file_total
        dir_stats[dir_key][1] += int(file_total * pct / 100)

    per_target = []
    for dir_name, (total, covered) in sorted(dir_stats.items(), key=lambda x: x[1][0], reverse=True):
        if total == 0:
            continue
        pct = covered / total * 100
        per_target.append(f"{dir_name}: {pct:.1f}%")

    return per_target


def _file_matches_patterns(filepath, patterns):
    """Check if a filepath matches any exclusion pattern."""
    basename = os.path.basename(filepath)
    for pattern in patterns:
        if fnmatch.fnmatch(filepath, pattern):
            return True
        if fnmatch.fnmatch(basename, pattern):
            return True
        if "/" in pattern and fnmatch.fnmatch(filepath, f"*{pattern}*"):
            return True
    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shorten_path(filepath):
    """Shorten a file path for display."""
    filepath = filepath.replace("\\", "/")
    # Remove common prefixes and URI schemes
    for prefix in ["file://", "package:"]:
        if filepath.startswith(prefix):
            filepath = filepath[len(prefix):]
    for prefix in ["/lib/", "lib/", "./lib/", "./", "/"]:
        idx = filepath.find(prefix)
        if idx >= 0:
            filepath = filepath[idx + len(prefix):]
            break
    parts = filepath.split("/")
    if len(parts) > 4:
        return "/".join(parts[-4:])
    return filepath


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_table(results, coverage=None):
    """Print results in the pipeline contract format."""
    if not results or results["total"] == 0:
        print("\nNo test results parsed. Check diagnostic info above.")
        return

    total = results["total"]
    passed = results["passed"]
    failed = results["failed"]
    skipped = results["skipped"]
    failures = results["failures"]

    coverage_str = f" | Coverage: {coverage['overall']:.1f}%" if coverage else ""
    skip_str = f", Skipped: {skipped}" if skipped else ""
    print(f"\nSummary: Total: {total}, Passed: {passed}, Failed: {failed}{skip_str}{coverage_str}\n")

    if coverage and coverage.get("per_target"):
        print("Coverage:  " + "  |  ".join(coverage["per_target"]))
        if coverage.get("excluded_lines"):
            print(f"Excluded:  {coverage['excluded_lines']} lines ({coverage['excluded_pct']:.1f}% covered) -- filtered by --exclude-from-coverage")
        print()

    if not failures:
        if failed == 0:
            print("All tests passed.")
        return

    # Print failure table
    sw = max(len(f["suite"]) for f in failures) if failures else 0
    tw = max(len(f["test"]) for f in failures) if failures else 0
    sw = max(sw, 5)
    tw = max(tw, 4)

    header = f"{'Suite':<{sw}}  {'Test':<{tw}}"
    print(header)
    print("-" * min(sw + tw + 4, 120))

    for f in failures:
        print(f"{f['suite']:<{sw}}  {f['test']:<{tw}}")
        if f.get("msg"):
            print(f"   > {f['msg']}")

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run Flutter tests and show minimal pass/fail table."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--test-dir", default=None, help="Specific test directory to run (e.g. test/unit)")
    parser.add_argument("--no-coverage", action="store_true", help="Disable code coverage collection")
    parser.add_argument(
        "--exclude-from-coverage",
        nargs="+",
        metavar="PATTERN",
        help="Glob patterns for files to exclude from coverage (e.g. '*.g.dart' '*.freezed.dart')",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    collect_coverage = not args.no_coverage

    print(f"Project dir: {project_dir}")

    # Verify pubspec.yaml exists
    if not os.path.exists(os.path.join(project_dir, "pubspec.yaml")):
        print("ERROR: No pubspec.yaml found in:")
        print(f"  {project_dir}")
        sys.exit(1)

    flutter_cmd = find_flutter()
    print(f"Flutter: {' '.join(flutter_cmd)}")

    stdout, stderr, returncode = run_tests(
        project_dir, flutter_cmd,
        coverage=collect_coverage,
        test_dir=args.test_dir,
    )

    # Parse results from --machine JSON output (stdout)
    results = parse_machine_output(stdout)

    # Fallback to text parsing from stderr if machine output didn't work
    if not results or results["total"] == 0:
        results = parse_fallback(stderr)

    # Parse coverage
    coverage = None
    if collect_coverage:
        # Default exclusions for generated files
        exclude_patterns = list(args.exclude_from_coverage or [])
        default_excludes = ["*.g.dart", "*.freezed.dart", "*.gen.dart"]
        for pattern in default_excludes:
            if pattern not in exclude_patterns:
                exclude_patterns.append(pattern)

        coverage = parse_coverage(project_dir, exclude_patterns=exclude_patterns)

    print_table(results, coverage=coverage)

    # Diagnostic output when no results were parsed
    if not results or results["total"] == 0:
        print("\n--- Diagnostic Info ---")
        if returncode != 0:
            print(f"flutter test returned exit code {returncode}")
        else:
            print("Tests ran but no results were parsed.")

        # Show stderr (flutter test puts human-readable output there when --machine is used)
        lines = stderr.strip().splitlines()
        filtered = [l for l in lines if l.strip()]
        display = filtered if filtered else lines
        print("\nLast 50 lines of output:")
        print("\n".join(display[-50:]))

        if returncode != 0:
            sys.exit(1)
        return

    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
