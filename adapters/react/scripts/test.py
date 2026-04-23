#!/usr/bin/env python3
"""
Run React/TypeScript tests (Jest or Vitest) and output a minimal results table.

Usage examples:
  # Auto-detect everything
  python test.py --project-dir .

  # Specific test script from package.json
  python test.py --project-dir . --scheme test:unit

  # Without coverage
  python test.py --project-dir . --no-coverage

  # Exclude patterns from coverage
  python test.py --project-dir . --exclude-from-coverage '*.config.*' '*.d.ts' '**/index.ts'
"""

import subprocess
import sys
import re
import argparse
import os
import json
import fnmatch


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------

def detect_package_manager(project_dir):
    """
    Detect the package manager by looking for lock files.
    Priority: pnpm > yarn > bun > npm (fallback).
    """
    checks = [
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
        ("package-lock.json", "npm"),
    ]
    for lockfile, pm in checks:
        if os.path.exists(os.path.join(project_dir, lockfile)):
            return pm
    return "npm"


# ---------------------------------------------------------------------------
# Test framework detection
# ---------------------------------------------------------------------------

def detect_test_framework(project_dir):
    """
    Detect the test framework: 'vitest' or 'jest'.
    Checks config files first, then package.json dependencies.
    """
    entries = os.listdir(project_dir)

    # Check for Vitest config files
    vitest_configs = [
        "vitest.config.ts", "vitest.config.js", "vitest.config.mts", "vitest.config.mjs",
        "vitest.workspace.ts", "vitest.workspace.js",
    ]
    for cfg in vitest_configs:
        if cfg in entries:
            return "vitest"

    # Check for Jest config files
    jest_configs = [
        "jest.config.ts", "jest.config.js", "jest.config.mjs", "jest.config.cjs",
        "jest.config.json",
    ]
    for cfg in jest_configs:
        if cfg in entries:
            return "jest"

    # Fall back to checking package.json
    pkg_path = os.path.join(project_dir, "package.json")
    if os.path.exists(pkg_path):
        with open(pkg_path) as f:
            pkg = json.load(f)

        # Check for "jest" config key in package.json
        if "jest" in pkg:
            return "jest"

        # Check dependencies
        all_deps = {}
        all_deps.update(pkg.get("dependencies", {}))
        all_deps.update(pkg.get("devDependencies", {}))

        if "vitest" in all_deps:
            return "vitest"
        if "jest" in all_deps or "@jest/core" in all_deps:
            return "jest"

    return "jest"  # Default fallback


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def run_tests(project_dir, pm, framework, scheme=None, coverage=True):
    """
    Run tests and return (stdout+stderr, returncode, json_output_path).
    """
    json_output_path = os.path.join(project_dir, ".pipeline-test-results.json")

    # If a specific script is requested from package.json, use it
    if scheme:
        pkg_path = os.path.join(project_dir, "package.json")
        if os.path.exists(pkg_path):
            with open(pkg_path) as f:
                scripts = json.load(f).get("scripts", {})
            if scheme in scripts:
                # Run the package.json script with extra flags
                if pm == "npm":
                    cmd = ["npm", "run", scheme, "--"]
                elif pm == "yarn":
                    cmd = ["yarn", scheme]
                elif pm == "pnpm":
                    cmd = ["pnpm", "run", scheme, "--"]
                elif pm == "bun":
                    cmd = ["bun", "run", scheme, "--"]
                else:
                    cmd = ["npm", "run", scheme, "--"]

                if framework == "vitest":
                    # Keep default reporter active so parse_fallback has text to match
                    # if JSON parsing fails. --outputFile.json disambiguates output
                    # when multiple reporters are active.
                    cmd += [
                        "--reporter=default",
                        "--reporter=json",
                        f"--outputFile.json={json_output_path}",
                    ]
                    if coverage:
                        cmd += ["--coverage", "--coverage.reporter=json"]
                else:
                    cmd += [f"--json", f"--outputFile={json_output_path}"]
                    if coverage:
                        cmd += ["--coverage"]

                print(f"Running: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd, cwd=project_dir, capture_output=True, text=True,
                    timeout=600, env={**os.environ, "CI": "true", "FORCE_COLOR": "0"}
                )
                return result.stdout + result.stderr, result.returncode, json_output_path

    # Direct invocation via npx/pnpm exec/yarn/bunx
    env = {**os.environ, "CI": "true", "FORCE_COLOR": "0"}

    if framework == "vitest":
        if pm == "pnpm":
            cmd = ["pnpm", "exec", "vitest", "run"]
        elif pm == "yarn":
            cmd = ["yarn", "vitest", "run"]
        elif pm == "bun":
            cmd = ["bun", "run", "vitest", "run"]
        else:
            cmd = ["npx", "vitest", "run"]

        cmd += [
            "--reporter=default",
            "--reporter=json",
            f"--outputFile.json={json_output_path}",
        ]
        if coverage:
            cmd += ["--coverage", "--coverage.reporter=json"]
    else:
        # Jest
        if pm == "pnpm":
            cmd = ["pnpm", "exec", "jest"]
        elif pm == "yarn":
            cmd = ["yarn", "jest"]
        elif pm == "bun":
            cmd = ["bun", "run", "jest"]
        else:
            cmd = ["npx", "jest"]

        cmd += ["--json", f"--outputFile={json_output_path}"]
        if coverage:
            cmd += ["--coverage", "--coverageReporters=json-summary"]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True,
        timeout=600, env=env,
    )
    return result.stdout + result.stderr, result.returncode, json_output_path


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

def parse_jest_json(json_path, raw_output, diagnostics=None):
    """
    Parse Jest JSON output.
    Returns same shape as parse_vitest_json.
    """
    data = _load_json_results(json_path, raw_output, diagnostics)
    if not data:
        return None

    total = data.get("numTotalTests", 0)
    passed = data.get("numPassedTests", 0)
    failed = data.get("numFailedTests", 0)
    skipped = data.get("numPendingTests", 0) + data.get("numTodoTests", 0)

    failures = []
    for suite in data.get("testResults", []):
        suite_name = _shorten_path(suite.get("name", ""))
        for test in suite.get("assertionResults", []):
            if test.get("status") == "failed":
                test_name = " > ".join(test.get("ancestorTitles", [])) + " > " + test.get("title", "")
                test_name = test_name.strip(" > ")
                messages = test.get("failureMessages", [])
                msg = messages[0].split("\n")[0].strip()[:160] if messages else "Unknown failure"
                failures.append({
                    "suite": suite_name,
                    "test": test_name,
                    "msg": msg,
                })

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def parse_vitest_json(json_path, raw_output, diagnostics=None):
    """
    Parse Vitest JSON output.
    Returns same shape as parse_jest_json.
    """
    data = _load_json_results(json_path, raw_output, diagnostics)
    if not data:
        return None

    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures = []

    # Vitest JSON structure: { testResults: [...] } or { numTotalTests, ... }
    # The format depends on the reporter version
    test_results = data.get("testResults", [])

    for suite in test_results:
        suite_name = _shorten_path(suite.get("name", ""))

        for test in suite.get("assertionResults", []):
            total += 1
            status = test.get("status", "")
            if status == "passed":
                passed += 1
            elif status == "failed":
                failed += 1
                test_name = " > ".join(test.get("ancestorTitles", [])) + " > " + test.get("title", "")
                test_name = test_name.strip(" > ")
                messages = test.get("failureMessages", [])
                msg = messages[0].split("\n")[0].strip()[:160] if messages else "Unknown failure"
                failures.append({
                    "suite": suite_name,
                    "test": test_name,
                    "msg": msg,
                })
            elif status in ("pending", "skipped", "todo"):
                skipped += 1
                total += 1  # Count skipped in total

    # If the above didn't work, try top-level summary keys
    if total == 0:
        total = data.get("numTotalTests", 0)
        passed = data.get("numPassedTests", 0)
        failed = data.get("numFailedTests", 0)
        skipped = data.get("numPendingTests", 0) + data.get("numTodoTests", 0)

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def _load_json_results(json_path, raw_output, diagnostics=None):
    """Try to load JSON from file, then from raw output as fallback.

    If ``diagnostics`` is a list, appends human-readable reasons when the
    JSON file exists but can't be parsed — so failures don't vanish silently.
    """
    if json_path and os.path.exists(json_path):
        try:
            with open(json_path) as f:
                content = f.read()
            stripped = content.strip()
            if not stripped:
                if diagnostics is not None:
                    diagnostics.append(f"JSON output file is empty: {json_path}")
            else:
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError as e:
                    if diagnostics is not None:
                        diagnostics.append(f"JSON output file is malformed ({e}): {json_path}")
        except IOError as e:
            if diagnostics is not None:
                diagnostics.append(f"Could not read JSON output file ({e}): {json_path}")

    # Fallback: try to extract JSON from raw output
    # Jest sometimes writes JSON to stdout
    if raw_output:
        # Find the outermost JSON object
        start = raw_output.find("{")
        if start >= 0:
            brace_count = 0
            end = start
            for i, ch in enumerate(raw_output[start:], start):
                if ch == "{":
                    brace_count += 1
                elif ch == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            try:
                return json.loads(raw_output[start:end])
            except json.JSONDecodeError:
                pass

    return None


def parse_fallback(raw_output):
    """
    Fallback parser when JSON output is unavailable.
    Parses text output for pass/fail counts.
    """
    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures = []

    # Jest summary line: "Tests:   2 failed, 3 passed, 5 total"
    # Token-based parse so any ordering of failed/passed/skipped works.
    jest_summary_line = re.search(r"^\s*Tests:.*?\btotal\b", raw_output, re.MULTILINE)
    if jest_summary_line:
        line = jest_summary_line.group(0)
        for m in re.finditer(r"(\d+)\s+(failed|passed|skipped|todo|total)", line):
            n, kind = int(m.group(1)), m.group(2)
            if kind == "failed":
                failed = n
            elif kind == "passed":
                passed = n
            elif kind in ("skipped", "todo"):
                skipped += n
            elif kind == "total":
                total = n

    # Vitest summary line: "Tests  2 failed | 3 passed (5)" or "Tests  5 passed (5)"
    # Token-based parse; the "(N)" at the end is authoritative for the total.
    if total == 0:
        vitest_summary_line = re.search(
            r"^\s*Tests\s+.*?\(\s*\d+\s*\)\s*$", raw_output, re.MULTILINE,
        )
        if vitest_summary_line:
            line = vitest_summary_line.group(0)
            for m in re.finditer(r"(\d+)\s+(failed|passed|skipped|todo)", line):
                n, kind = int(m.group(1)), m.group(2)
                if kind == "failed":
                    failed = n
                elif kind == "passed":
                    passed = n
                elif kind in ("skipped", "todo"):
                    skipped += n
            paren = re.search(r"\(\s*(\d+)\s*\)\s*$", line)
            if paren:
                total = int(paren.group(1))

    # Extract failure details from text output
    fail_pattern = re.compile(r"(?:FAIL|FAILED)\s+([^\n]+)\n([\s\S]*?)(?=(?:FAIL|PASS|Test Suites:|$))")
    for m in fail_pattern.finditer(raw_output):
        suite = _shorten_path(m.group(1).strip())
        detail = m.group(2)
        test_match = re.search(r"[x\u2717]\s+(.+?)(?:\n|$)", detail)
        test_name = test_match.group(1).strip() if test_match else "Unknown test"
        msg_match = re.search(r"(?:Expected|Received|Error|AssertionError).*?$", detail, re.MULTILINE)
        msg = msg_match.group(0).strip()[:160] if msg_match else ""
        failures.append({"suite": suite, "test": test_name, "msg": msg})

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
    Parse coverage from JSON summary files produced by Jest or Vitest.
    Returns dict with 'overall' (float %), 'per_target' (list of strings), or None.
    """
    # Look for coverage JSON summary in common locations
    candidates = [
        os.path.join(project_dir, "coverage", "coverage-summary.json"),
        os.path.join(project_dir, "coverage", "coverage-final.json"),
    ]

    summary_data = None
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    summary_data = json.load(f)
                break
            except (json.JSONDecodeError, IOError):
                continue

    if not summary_data:
        return None

    # coverage-summary.json format: { "total": { "lines": { "total": N, "covered": N, "pct": N } }, "path/file.ts": { ... } }
    if "total" in summary_data and "lines" in summary_data.get("total", {}):
        return _parse_coverage_summary(summary_data, exclude_patterns)

    # coverage-final.json format: { "path/file.ts": { "s": {...}, "b": {...}, ... } }
    return _parse_coverage_final(summary_data, exclude_patterns)


def _parse_coverage_summary(data, exclude_patterns=None):
    """Parse coverage-summary.json format."""
    total_stmts = 0
    covered_stmts = 0
    excluded_stmts = 0
    excluded_covered = 0
    per_file = []

    for filepath, metrics in data.items():
        if filepath == "total":
            continue

        stmts = metrics.get("statements", metrics.get("lines", {}))
        file_total = stmts.get("total", 0)
        file_covered = stmts.get("covered", 0)

        if file_total == 0:
            continue

        short = _shorten_path(filepath)

        if exclude_patterns and _file_matches_patterns(filepath, exclude_patterns):
            excluded_stmts += file_total
            excluded_covered += file_covered
            continue

        total_stmts += file_total
        covered_stmts += file_covered
        pct = file_covered / file_total * 100
        per_file.append((short, pct, file_total))

    if total_stmts == 0:
        return None

    overall = covered_stmts / total_stmts * 100

    # Group by directory for per-target summary
    per_target = _group_by_directory(per_file)

    result = {"overall": overall, "per_target": per_target}
    if exclude_patterns and excluded_stmts > 0:
        result["excluded_lines"] = excluded_stmts
        result["excluded_pct"] = excluded_covered / excluded_stmts * 100
    return result


def _parse_coverage_final(data, exclude_patterns=None):
    """Parse coverage-final.json format (statement map based)."""
    total_stmts = 0
    covered_stmts = 0
    excluded_stmts = 0
    excluded_covered = 0
    per_file = []

    for filepath, file_data in data.items():
        s_map = file_data.get("s", {})
        file_total = len(s_map)
        file_covered = sum(1 for v in s_map.values() if v > 0)

        if file_total == 0:
            continue

        short = _shorten_path(filepath)

        if exclude_patterns and _file_matches_patterns(filepath, exclude_patterns):
            excluded_stmts += file_total
            excluded_covered += file_covered
            continue

        total_stmts += file_total
        covered_stmts += file_covered
        pct = file_covered / file_total * 100
        per_file.append((short, pct, file_total))

    if total_stmts == 0:
        return None

    overall = covered_stmts / total_stmts * 100
    per_target = _group_by_directory(per_file)

    result = {"overall": overall, "per_target": per_target}
    if exclude_patterns and excluded_stmts > 0:
        result["excluded_lines"] = excluded_stmts
        result["excluded_pct"] = excluded_covered / excluded_stmts * 100
    return result


def _group_by_directory(per_file):
    """Group per-file coverage into per-directory summaries."""
    dir_stats = {}  # dir -> (total_stmts, total_covered_stmts_approx)
    for short_path, pct, file_total in per_file:
        parts = short_path.split("/")
        # Use the first meaningful directory as the grouping key
        if len(parts) >= 2:
            dir_key = parts[0] if parts[0] != "src" else (parts[1] if len(parts) > 2 else "src")
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
    # Remove common prefixes
    for prefix in ["/src/", "src/", "./src/", "./", "/"]:
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
            print(f"Excluded:  {coverage['excluded_lines']} statements ({coverage['excluded_pct']:.1f}% covered) -- filtered by --exclude-from-coverage")
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
        description="Run React/TypeScript tests and show minimal pass/fail table."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--scheme", default=None, help="Test script name from package.json (auto-detected if omitted)")
    parser.add_argument("--no-coverage", action="store_true", help="Disable code coverage collection")
    parser.add_argument(
        "--exclude-from-coverage",
        nargs="+",
        metavar="PATTERN",
        help="Glob patterns for files to exclude from coverage (e.g. '*.config.*' '*.d.ts' '**/index.ts')",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    collect_coverage = not args.no_coverage

    print(f"Project dir: {project_dir}")

    pm = detect_package_manager(project_dir)
    print(f"Package manager: {pm}")

    framework = detect_test_framework(project_dir)
    print(f"Test framework: {framework}")

    if args.scheme:
        print(f"Test script: {args.scheme}")

    raw_output, returncode, json_path = run_tests(
        project_dir, pm, framework,
        scheme=args.scheme,
        coverage=collect_coverage,
    )

    # Parse results. Collect JSON-load diagnostics so we can report why parsing
    # failed (empty file, malformed JSON) rather than silently falling through.
    json_diagnostics = []
    if framework == "vitest":
        results = parse_vitest_json(json_path, raw_output, json_diagnostics)
    else:
        results = parse_jest_json(json_path, raw_output, json_diagnostics)

    # Fallback to text parsing if JSON didn't work
    if not results or results["total"] == 0:
        results = parse_fallback(raw_output)

    # Parse coverage
    coverage = parse_coverage(
        project_dir,
        exclude_patterns=args.exclude_from_coverage,
    ) if collect_coverage else None

    print_table(results, coverage=coverage)

    parsed_ok = bool(results) and results["total"] > 0

    # Diagnostic output when no results were parsed OR the test runner exited
    # non-zero despite parsed results (coverage threshold, setup warnings, etc.).
    needs_diagnostic = (not parsed_ok) or returncode != 0
    if needs_diagnostic:
        print("\n--- Diagnostic Info ---")
        if returncode != 0:
            print(f"Test runner returned exit code {returncode}")
        if not parsed_ok:
            print("Tests ran but no results were parsed.")
        for diag in json_diagnostics:
            print(diag)
        if json_path and os.path.exists(json_path):
            print(f"JSON output file preserved for inspection: {json_path}")

        lines = raw_output.strip().splitlines()
        # Only strip deep-nested stack frames ("    at ... node_modules/..."),
        # not top-level error messages that happen to mention node_modules —
        # those are often the only clue to vitest setup failures.
        node_stack_re = re.compile(r"^\s+at\s+.*node_modules/")
        filtered = [l for l in lines if l.strip() and not node_stack_re.match(l)]
        display = filtered if filtered else lines
        print("\nLast 50 lines of output:")
        print("\n".join(display[-50:]))

    # Clean up JSON output file last, so diagnostics above can reference it.
    if json_path and os.path.exists(json_path):
        try:
            os.remove(json_path)
        except OSError:
            pass

    # Exit 1 only when we genuinely can't parse results or there are failures.
    # A non-zero returncode with passing tests (e.g. coverage threshold warning)
    # should not mask a successful run.
    if not parsed_ok:
        sys.exit(1)
    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
