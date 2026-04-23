#!/usr/bin/env python3
"""
Run Python tests with pytest and output results in pipeline contract format.

Usage:
  python test.py [--project-dir /path/to/project] [--scheme <suite>] [--no-coverage] [--exclude-from-coverage '<pattern>']

Output format:
  Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%
"""

import subprocess
import sys
import re
import argparse
import os
import json


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def detect_test_config(project_dir):
    """Detect test configuration from project files."""
    info = {
        "has_pytest_cov": False,
        "source_package": None,
        "test_dirs": [],
        "pytest_args": [],
        "coverage_config": {},
    }

    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    setup_cfg_path = os.path.join(project_dir, "setup.cfg")

    # Check for pytest-cov availability
    try:
        result = subprocess.run(
            ["python3", "-c", "import pytest_cov"],
            cwd=project_dir, capture_output=True, text=True, check=False
        )
        info["has_pytest_cov"] = result.returncode == 0
    except Exception:
        pass

    # Detect source package for coverage
    if os.path.isdir(os.path.join(project_dir, "src")):
        # src layout — find packages inside src/
        for entry in os.listdir(os.path.join(project_dir, "src")):
            pkg_path = os.path.join(project_dir, "src", entry)
            if os.path.isdir(pkg_path) and os.path.exists(os.path.join(pkg_path, "__init__.py")):
                info["source_package"] = entry
                break
        if not info["source_package"]:
            info["source_package"] = "src"
    else:
        # Flat layout — find first package
        for entry in os.listdir(project_dir):
            full = os.path.join(project_dir, entry)
            if (
                os.path.isdir(full)
                and not entry.startswith(".")
                and not entry.startswith("_")
                and entry not in ("tests", "test", "docs", "scripts", "migrations",
                                  "venv", "env", ".venv", "node_modules", "__pycache__",
                                  "htmlcov", ".mypy_cache", ".ruff_cache", ".pytest_cache")
                and os.path.exists(os.path.join(full, "__init__.py"))
            ):
                info["source_package"] = entry
                break

    # Find test directories
    for candidate in ("tests", "test"):
        if os.path.isdir(os.path.join(project_dir, candidate)):
            info["test_dirs"].append(candidate)

    # Parse pyproject.toml for pytest config
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, "r") as f:
                content = f.read()

            # Extract testpaths if configured
            testpaths_match = re.search(r'testpaths\s*=\s*\[([^\]]+)\]', content)
            if testpaths_match:
                paths = re.findall(r'"([^"]+)"', testpaths_match.group(1))
                if paths:
                    info["test_dirs"] = paths

            # Extract coverage source
            cov_source_match = re.search(r'\[tool\.coverage\.run\][^[]*source\s*=\s*\[([^\]]+)\]', content, re.DOTALL)
            if cov_source_match:
                sources = re.findall(r'"([^"]+)"', cov_source_match.group(1))
                if sources:
                    info["coverage_config"]["source"] = sources

            # Extract coverage omit patterns
            cov_omit_match = re.search(r'\[tool\.coverage\.run\][^[]*omit\s*=\s*\[([^\]]+)\]', content, re.DOTALL)
            if cov_omit_match:
                omits = re.findall(r'"([^"]+)"', cov_omit_match.group(1))
                if omits:
                    info["coverage_config"]["omit"] = omits

        except Exception:
            pass

    # Parse setup.cfg for pytest config
    if os.path.exists(setup_cfg_path):
        try:
            with open(setup_cfg_path, "r") as f:
                cfg_content = f.read()
            testpaths_match = re.search(r'testpaths\s*=\s*(.+)', cfg_content)
            if testpaths_match and not info["test_dirs"]:
                info["test_dirs"] = testpaths_match.group(1).strip().split()
        except Exception:
            pass

    return info


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def run_tests(project_dir, scheme=None, coverage=True, exclude_patterns=None, test_config=None):
    """Run pytest and return (stdout+stderr, returncode, coverage_json_path)."""
    cmd = ["python3", "-m", "pytest", "--tb=short", "-q"]

    # Add coverage flags if enabled and pytest-cov is available
    coverage_json_path = None
    if coverage and test_config and test_config["has_pytest_cov"]:
        cov_target = test_config.get("source_package")

        # Use coverage source from config, or auto-detected package
        cov_sources = test_config.get("coverage_config", {}).get("source", [])
        if cov_sources:
            for src in cov_sources:
                cmd.extend(["--cov", src])
        elif cov_target:
            cmd.extend(["--cov", cov_target])
        else:
            cmd.append("--cov")

        coverage_json_path = os.path.join(project_dir, ".coverage_report.json")
        cmd.extend(["--cov-report", f"json:{coverage_json_path}"])
        cmd.extend(["--cov-report", "term-missing:skip-covered"])

        # Apply exclude patterns via --cov-config or inline omit
        if exclude_patterns:
            omit_value = ",".join(exclude_patterns)
            cmd.extend(["--cov-config", "/dev/null"])  # Ignore existing config
            cmd.extend(["--override-ini", f"cov_config="])
            # Use inline --cov-branch is not needed; just add omit patterns
            for pattern in exclude_patterns:
                cmd.extend(["--cov-config-omit", pattern])

    # Add scheme as marker filter if provided (e.g., --scheme "not slow")
    if scheme:
        # If scheme looks like a marker expression, use -m
        if any(kw in scheme for kw in ("not ", "and ", "or ", "slow", "integration", "e2e", "unit")):
            cmd.extend(["-m", scheme])
        else:
            # Treat as a test path or pattern
            cmd.append(scheme)

    # Add test directories if no specific target given
    if not scheme and test_config and test_config["test_dirs"]:
        cmd.extend(test_config["test_dirs"])

    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )

    return result.stdout + result.stderr, result.returncode, coverage_json_path


# ---------------------------------------------------------------------------
# Coverage parsing
# ---------------------------------------------------------------------------

def parse_coverage(coverage_json_path, exclude_patterns=None):
    """
    Parse coverage.json and return coverage data.
    Returns dict with 'overall' (float %), 'per_module' (list of strings), or None.
    """
    if not coverage_json_path or not os.path.exists(coverage_json_path):
        return None

    try:
        with open(coverage_json_path, "r") as f:
            data = json.load(f)

        totals = data.get("totals", {})
        files = data.get("files", {})

        if not totals:
            return None

        # Calculate per-module coverage
        # Group files by top-level module
        module_stats = {}  # module_name -> {covered_lines, num_statements}
        excluded_stats = {"covered_lines": 0, "num_statements": 0}

        for filepath, file_data in files.items():
            summary = file_data.get("summary", {})
            covered = summary.get("covered_lines", 0)
            statements = summary.get("num_statements", 0)

            if statements == 0:
                continue

            # Check if this file should be excluded
            if exclude_patterns and _file_matches_any_pattern(filepath, exclude_patterns):
                excluded_stats["covered_lines"] += covered
                excluded_stats["num_statements"] += statements
                continue

            # Extract module name (first directory component or filename)
            parts = filepath.replace("\\", "/").split("/")
            # Skip common prefixes
            while parts and parts[0] in ("src", ".", ""):
                parts = parts[1:]
            module = parts[0] if parts else filepath

            if module not in module_stats:
                module_stats[module] = {"covered_lines": 0, "num_statements": 0}
            module_stats[module]["covered_lines"] += covered
            module_stats[module]["num_statements"] += statements

        # Calculate overall (excluding excluded files)
        total_covered = sum(m["covered_lines"] for m in module_stats.values())
        total_statements = sum(m["num_statements"] for m in module_stats.values())

        if total_statements == 0:
            return None

        overall_pct = (total_covered / total_statements) * 100

        # Format per-module coverage
        per_module = []
        for name in sorted(module_stats.keys(), key=lambda n: module_stats[n]["num_statements"], reverse=True):
            stats = module_stats[name]
            if stats["num_statements"] > 0:
                pct = (stats["covered_lines"] / stats["num_statements"]) * 100
                per_module.append(f"{name}: {pct:.1f}%")

        result = {"overall": overall_pct, "per_module": per_module}

        if exclude_patterns and excluded_stats["num_statements"] > 0:
            result["excluded_lines"] = excluded_stats["num_statements"]
            result["excluded_pct"] = (
                excluded_stats["covered_lines"] / excluded_stats["num_statements"]
            ) * 100

        return result

    except Exception as e:
        print(f"Warning: Could not parse coverage data ({e})")
        return None


def _file_matches_any_pattern(filepath, patterns):
    """Check if a file path matches any of the exclusion patterns."""
    import fnmatch

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
# Result parsing
# ---------------------------------------------------------------------------

def parse_results(output):
    """
    Parse pytest output for test counts and failure details.
    Returns (total, passed, failed, error, failures_dict).
    """
    total = 0
    passed = 0
    failed = 0
    errors = 0
    failures = {}

    # Locate the last pytest summary line — handles any token order, e.g.
    # "17 failed, 520 passed in 2.00s" as well as "520 passed, 17 failed in 2.00s"
    summary_line = None
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if (re.search(r'\d+\s+(?:passed|failed|error)', stripped) and
                re.search(r'\bin\s+[\d.]+\s*s\b', stripped)):
            summary_line = stripped
            break

    if summary_line:
        _plural = {'errors': 'error', 'warnings': 'warning'}
        for m in re.finditer(
            r'(\d+)\s+(passed|failed|errors?|skipped|deselected|warnings?)',
            summary_line,
        ):
            n, kind = m.groups()
            key = _plural.get(kind, kind)
            if key == 'passed':
                passed = int(n)
            elif key == 'failed':
                failed = int(n)
            elif key == 'error':
                errors = int(n)
        total = passed + failed + errors

    # Also try the short format: "N passed" or "N failed"
    if total == 0:
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        error_match = re.search(r"(\d+) error", output)
        if passed_match:
            passed = int(passed_match.group(1))
        if failed_match:
            failed = int(failed_match.group(1))
        if error_match:
            errors = int(error_match.group(1))
        total = passed + failed + errors

    # Parse failure details from FAILURES section
    # Pattern: FAILED tests/test_foo.py::test_bar - AssertionError: message
    fail_pattern = re.compile(
        r"FAILED\s+(\S+?)(?:\s+-\s+(.+))?$", re.MULTILINE
    )
    for m in fail_pattern.finditer(output):
        test_id = m.group(1)
        reason = m.group(2) or ""
        # Shorten test_id: tests/test_foo.py::TestClass::test_method -> TestClass::test_method
        parts = test_id.split("::")
        if len(parts) >= 2:
            short_id = "::".join(parts[-2:]) if len(parts) > 2 else "::".join(parts)
        else:
            short_id = test_id
        failures[short_id] = reason.strip()[:160]

    # Parse short failure output (pytest -q format)
    # FAILED tests/test_foo.py::test_bar
    if not failures:
        short_fail_pattern = re.compile(r"^FAILED (\S+)$", re.MULTILINE)
        for m in short_fail_pattern.finditer(output):
            test_id = m.group(1)
            parts = test_id.split("::")
            short_id = "::".join(parts[-2:]) if len(parts) > 2 else test_id
            failures[short_id] = ""

    # Parse individual assertion errors from the FAILURES section
    failure_section = re.search(r"={3,} FAILURES ={3,}(.*?)(?:={3,}|$)", output, re.DOTALL)
    if failure_section:
        section_text = failure_section.group(1)
        # Each failure block starts with ___ test_name ___
        test_blocks = re.split(r"_{3,}\s+(.+?)\s+_{3,}", section_text)
        # test_blocks: ['', test_name_1, block_1, test_name_2, block_2, ...]
        for i in range(1, len(test_blocks) - 1, 2):
            test_name = test_blocks[i].strip()
            block = test_blocks[i + 1]

            # Extract the assertion error or last error line
            error_lines = []
            for line in block.splitlines():
                stripped = line.strip()
                if stripped.startswith("E "):
                    error_lines.append(stripped[2:].strip())
                elif "AssertionError" in stripped or "Error" in stripped:
                    error_lines.append(stripped)

            if error_lines:
                reason = " | ".join(error_lines[:3])[:160]
                # Map test_name to our short_id format
                parts = test_name.split("::")
                short_id = "::".join(parts[-2:]) if len(parts) > 2 else test_name
                if short_id not in failures or not failures[short_id]:
                    failures[short_id] = reason

    return total, passed, failed, errors, failures


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_table(total, passed, failed, errors, failures, coverage=None):
    """Print results in pipeline contract format."""
    if total == 0:
        print("\nNo test results found. Check diagnostic info above.")
        return

    coverage_str = f" | Coverage: {coverage['overall']:.1f}%" if coverage else ""
    print(f"\nSummary: Total: {total}, Passed: {passed}, Failed: {failed + errors}{coverage_str}\n")

    # Per-module coverage
    if coverage and coverage.get("per_module"):
        print("Coverage:  " + "  |  ".join(coverage["per_module"]))
        if coverage.get("excluded_lines"):
            print(
                f"Excluded:  {coverage['excluded_lines']} statements "
                f"({coverage['excluded_pct']:.1f}% covered) "
                f"-- filtered by --exclude-from-coverage"
            )
        print()

    if failed + errors == 0:
        print("All tests passed.")
        return

    # Print failure table
    if not failures:
        print(f"{failed + errors} test(s) failed. Run tests manually for details.\n")
        return

    tw = max(len(k) for k in failures.keys()) + 2
    header = f"{'Test':<{tw}} {'Reason'}"
    print(header)
    print("-" * min(len(header) + 80, 140))

    for test_id, reason in failures.items():
        if reason:
            print(f"{test_id:<{tw}} {reason}")
        else:
            print(f"{test_id:<{tw}} (no details captured)")

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run pytest and show results in pipeline contract format."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument(
        "--scheme",
        default=None,
        help="Test suite filter: marker expression (e.g. 'not slow'), path, or pattern"
    )
    parser.add_argument("--no-coverage", action="store_true", help="Disable code coverage collection")
    parser.add_argument(
        "--exclude-from-coverage",
        nargs="+",
        metavar="PATTERN",
        help="Glob patterns for files to exclude from coverage (e.g. '*/migrations/*' '*_generated.py')"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    collect_coverage = not args.no_coverage

    print(f"Project dir: {project_dir}")
    if args.scheme:
        print(f"Scheme:      {args.scheme}")

    if not os.path.isdir(project_dir):
        print(f"ERROR: Project directory does not exist: {project_dir}")
        sys.exit(1)

    test_config = detect_test_config(project_dir)
    print(f"pytest-cov:  {'available' if test_config['has_pytest_cov'] else 'not found'}")
    if test_config["source_package"]:
        print(f"Source pkg:  {test_config['source_package']}")
    if test_config["test_dirs"]:
        print(f"Test dirs:   {test_config['test_dirs']}")

    output, returncode, coverage_json_path = run_tests(
        project_dir,
        scheme=args.scheme,
        coverage=collect_coverage,
        exclude_patterns=args.exclude_from_coverage,
        test_config=test_config,
    )

    total, passed, failed, errors, failures = parse_results(output)

    # Parse coverage
    coverage = None
    if collect_coverage and coverage_json_path:
        coverage = parse_coverage(
            coverage_json_path,
            exclude_patterns=args.exclude_from_coverage,
        )

        # Clean up coverage JSON
        try:
            if os.path.exists(coverage_json_path):
                os.remove(coverage_json_path)
        except Exception:
            pass

    # Also clean up .coverage file
    dot_coverage = os.path.join(project_dir, ".coverage")
    try:
        if os.path.exists(dot_coverage):
            os.remove(dot_coverage)
    except Exception:
        pass

    print_table(total, passed, failed, errors, failures, coverage=coverage)

    # Diagnostic output when no results were parsed
    if total == 0:
        print("\n--- Diagnostic Info ---")
        if returncode != 0:
            print(f"pytest returned exit code {returncode}")
        else:
            print("Tests ran but no results were parsed.")

        lines = output.strip().splitlines()
        # Show relevant lines
        display = [l for l in lines if l.strip()]
        print("\nLast 50 lines of output:")
        print("\n".join(display[-50:]))

        if returncode != 0:
            sys.exit(1)
    elif failed + errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
