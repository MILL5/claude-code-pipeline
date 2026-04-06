#!/usr/bin/env python3
"""
Run Android unit tests and output a minimal results table.

Usage examples:
  # Auto-detect everything
  python test.py --project-dir .

  # Specific module and variant
  python test.py --project-dir . --module app --variant debug

  # Without coverage
  python test.py --project-dir . --no-coverage
"""

import subprocess
import sys
import re
import argparse
import os
import xml.etree.ElementTree as ET
import glob as glob_mod


# ---------------------------------------------------------------------------
# Gradle wrapper detection
# ---------------------------------------------------------------------------

def find_gradlew(project_dir):
    """Find the Gradle wrapper executable."""
    gradlew = os.path.join(project_dir, "gradlew")
    if os.path.exists(gradlew):
        if not os.access(gradlew, os.X_OK):
            os.chmod(gradlew, 0o755)
        return gradlew

    parent_gradlew = os.path.join(os.path.dirname(project_dir), "gradlew")
    if os.path.exists(parent_gradlew):
        return parent_gradlew

    print("ERROR: Gradle wrapper (gradlew) not found in:")
    print(f"  {project_dir}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def run_tests(project_dir, gradlew, module, variant):
    """
    Run Gradle unit test task.
    Returns (stdout+stderr, returncode).
    """
    task = f":{module}:test{variant.capitalize()}UnitTest"
    print(f"Running: {gradlew} {task}")

    cmd = [gradlew, task, "--no-daemon", "--console=plain"]

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return result.stdout + result.stderr, result.returncode


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

def parse_junit_xml(project_dir, module, variant):
    """
    Parse JUnit XML test results produced by Gradle.
    Returns (total, passed, failed, skipped, failures).
    """
    # Gradle outputs JUnit XML in build/test-results/
    results_dir = os.path.join(
        project_dir, module, "build", "test-results",
        f"test{variant.capitalize()}UnitTest"
    )

    if not os.path.isdir(results_dir):
        # Try alternate paths
        for alt in [
            os.path.join(project_dir, module, "build", "test-results", "testDebugUnitTest"),
            os.path.join(project_dir, module, "build", "test-results", "test"),
            os.path.join(project_dir, "build", "test-results", f"test{variant.capitalize()}UnitTest"),
        ]:
            if os.path.isdir(alt):
                results_dir = alt
                break

    if not os.path.isdir(results_dir):
        return None

    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures = []

    xml_files = glob_mod.glob(os.path.join(results_dir, "TEST-*.xml"))

    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            suite_name = root.get("name", os.path.basename(xml_file))
            parts = suite_name.split(".")
            short_suite = ".".join(parts[-2:]) if len(parts) > 2 else suite_name

            suite_tests = int(root.get("tests", 0))
            suite_failures = int(root.get("failures", 0))
            suite_errors = int(root.get("errors", 0))
            suite_skipped = int(root.get("skipped", 0))

            total += suite_tests
            failed += suite_failures + suite_errors
            skipped += suite_skipped
            passed += suite_tests - suite_failures - suite_errors - suite_skipped

            # Extract individual failure details
            for testcase in root.findall("testcase"):
                failure = testcase.find("failure")
                error = testcase.find("error")
                fail_elem = failure if failure is not None else error

                if fail_elem is not None:
                    test_name = testcase.get("name", "unknown")
                    classname = testcase.get("classname", "")
                    cls_parts = classname.split(".")
                    short_class = cls_parts[-1] if cls_parts else classname

                    message = fail_elem.get("message", "")
                    if not message:
                        message = (fail_elem.text or "").split("\n")[0]
                    message = message.strip()[:160]

                    failures.append({
                        "suite": short_class,
                        "test": test_name,
                        "msg": message,
                    })

        except ET.ParseError as e:
            print(f"Warning: Could not parse {xml_file} ({e})")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def parse_fallback(output):
    """
    Fallback parser when XML results are unavailable.
    Parses Gradle text output.
    """
    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures = []

    # Gradle test summary: X tests completed, Y failed, Z skipped
    summary_pattern = re.compile(
        r"(\d+)\s+tests?\s+completed,?\s*(?:(\d+)\s+failed)?,?\s*(?:(\d+)\s+skipped)?"
    )
    for m in summary_pattern.finditer(output):
        total = int(m.group(1))
        failed = int(m.group(2) or 0)
        skipped = int(m.group(3) or 0)
        passed = total - failed - skipped

    # Individual test failures from Gradle output
    fail_pattern = re.compile(
        r"(\S+)\s*>\s*(\S+)(?:\([^)]*\))?\s+FAILED"
    )
    for m in fail_pattern.finditer(output):
        classname, test_name = m.groups()
        cls_parts = classname.split(".")
        short_class = cls_parts[-1] if cls_parts else classname
        failures.append({
            "suite": short_class,
            "test": test_name,
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

def parse_jacoco_coverage(project_dir, module, variant):
    """
    Parse JaCoCo XML coverage report.
    Returns dict with 'overall' (float %) and 'per_target' (list of strings), or None.
    """
    # Common JaCoCo report locations
    candidates = [
        os.path.join(project_dir, module, "build", "reports", "jacoco",
                     f"test{variant.capitalize()}UnitTest", "jacocoTestReport.xml"),
        os.path.join(project_dir, module, "build", "reports", "jacoco",
                     "jacocoTestReport", "jacocoTestReport.xml"),
        os.path.join(project_dir, module, "build", "reports", "jacoco", "test", "jacocoTestReport.xml"),
    ]

    xml_path = None
    for path in candidates:
        if os.path.exists(path):
            xml_path = path
            break

    if not xml_path:
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Overall coverage from root counters
        total_lines = 0
        covered_lines = 0

        for counter in root.findall("counter"):
            if counter.get("type") == "LINE":
                missed = int(counter.get("missed", 0))
                covered = int(counter.get("covered", 0))
                total_lines = missed + covered
                covered_lines = covered
                break

        if total_lines == 0:
            return None

        overall = covered_lines / total_lines * 100

        # Per-package coverage
        per_target = []
        for package in root.findall("package"):
            pkg_name = package.get("name", "").replace("/", ".")
            parts = pkg_name.split(".")
            short_pkg = ".".join(parts[-2:]) if len(parts) > 2 else pkg_name

            for counter in package.findall("counter"):
                if counter.get("type") == "LINE":
                    pkg_missed = int(counter.get("missed", 0))
                    pkg_covered = int(counter.get("covered", 0))
                    pkg_total = pkg_missed + pkg_covered
                    if pkg_total > 0:
                        pct = pkg_covered / pkg_total * 100
                        per_target.append((short_pkg, pct, pkg_total))
                    break

        # Sort by total lines descending, take top entries
        per_target.sort(key=lambda x: x[2], reverse=True)
        per_target_strs = [f"{name}: {pct:.1f}%" for name, pct, _ in per_target[:8]]

        return {"overall": overall, "per_target": per_target_strs}

    except ET.ParseError as e:
        print(f"Warning: Could not parse JaCoCo report ({e})")
        return None


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
        description="Run Android unit tests and show minimal pass/fail table."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--module", default="app", help="Gradle module name (default: app)")
    parser.add_argument("--variant", default="debug", help="Build variant (default: debug)")
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage report parsing")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    collect_coverage = not args.no_coverage

    print(f"Project dir: {project_dir}")

    gradlew = find_gradlew(project_dir)
    print(f"Gradle wrapper: {gradlew}")
    print(f"Module: {args.module}")
    print(f"Variant: {args.variant}")

    raw_output, returncode = run_tests(project_dir, gradlew, args.module, args.variant)

    # Parse results from JUnit XML
    results = parse_junit_xml(project_dir, args.module, args.variant)

    # Fallback to text parsing
    if not results or results["total"] == 0:
        results = parse_fallback(raw_output)

    # Parse coverage
    coverage = None
    if collect_coverage:
        coverage = parse_jacoco_coverage(project_dir, args.module, args.variant)

    print_table(results, coverage=coverage)

    # Diagnostic output when no results were parsed
    if not results or results["total"] == 0:
        print("\n--- Diagnostic Info ---")
        if returncode != 0:
            print(f"Gradle returned exit code {returncode}")
        else:
            print("Tests ran but no results were parsed.")

        lines = raw_output.strip().splitlines()
        filtered = [
            l for l in lines
            if l.strip()
            and not any(skip in l for skip in [
                "Downloading", "Download ", "> Task",
                "BUILD SUCCESSFUL", "actionable task",
            ])
        ]
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
