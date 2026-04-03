#!/usr/bin/env python3
"""
Run Android build (assemble + lint) and output errors in a minimal table.
Usage: python build.py [--project-dir /path/to/project] [--module app] [--variant debug]
"""

import subprocess
import sys
import re
import argparse
import os
import xml.etree.ElementTree as ET


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

    # Check parent directory (multi-module project where we're in a submodule)
    parent_gradlew = os.path.join(os.path.dirname(project_dir), "gradlew")
    if os.path.exists(parent_gradlew):
        return parent_gradlew

    print("ERROR: Gradle wrapper (gradlew) not found in:")
    print(f"  {project_dir}")
    print("Run 'gradle wrapper' to generate it.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Build steps
# ---------------------------------------------------------------------------

def run_assemble(project_dir, gradlew, module, variant):
    """
    Run Gradle assemble task.
    Returns (stdout+stderr, returncode).
    """
    task = f":{module}:assemble{variant.capitalize()}"
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


def run_lint(project_dir, gradlew, module, variant):
    """
    Run Android lint.
    Returns (stdout+stderr, returncode, lint_xml_path).
    """
    task = f":{module}:lint{variant.capitalize()}"
    print(f"Running: {gradlew} {task}")

    cmd = [gradlew, task, "--no-daemon", "--console=plain"]

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )

    # Lint XML output location
    lint_xml = os.path.join(
        project_dir, module, "build", "reports", f"lint-results-{variant}.xml"
    )
    if not os.path.exists(lint_xml):
        # Try alternate location
        lint_xml = os.path.join(
            project_dir, module, "build", "reports", "lint-results.xml"
        )

    return result.stdout + result.stderr, result.returncode, lint_xml


# ---------------------------------------------------------------------------
# Error parsing
# ---------------------------------------------------------------------------

def parse_gradle_errors(output):
    """
    Parse Gradle/Kotlin compiler errors from build output.
    """
    errors = []
    warnings = []
    seen = set()

    # Kotlin compiler errors: e: file:///path/to/File.kt:10:5 message
    kotlin_pattern = re.compile(
        r"([ew]):\s+(?:file://)?([^\s]+\.(?:kt|java)):(\d+):(\d+)\s+(.+)"
    )
    for m in kotlin_pattern.finditer(output):
        severity, filepath, line, col, message = m.groups()
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, message)
        if key in seen:
            continue
        seen.add(key)

        entry = {"file": short_path, "line": line, "col": col, "msg": message}
        if severity == "e":
            errors.append(entry)
        else:
            warnings.append(entry)

    # Java compiler errors: path/to/File.java:10: error: message
    java_pattern = re.compile(
        r"([^\s]+\.java):(\d+):\s+(error|warning):\s+(.+)"
    )
    for m in java_pattern.finditer(output):
        filepath, line, severity, message = m.groups()
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, message)
        if key in seen:
            continue
        seen.add(key)

        entry = {"file": short_path, "line": line, "col": "-", "msg": message}
        if severity == "error":
            errors.append(entry)
        else:
            warnings.append(entry)

    # Generic Gradle errors: > message or FAILURE: message
    gradle_error_pattern = re.compile(
        r"^(?:> |FAILURE: )(.+)$", re.MULTILINE
    )
    for m in gradle_error_pattern.finditer(output):
        msg = m.group(1).strip()[:120]
        if msg and not any(skip in msg.lower() for skip in ["build failed", "what went wrong"]):
            key = ("-", "-", msg)
            if key not in seen:
                seen.add(key)
                errors.append({"file": "-", "line": "-", "col": "-", "msg": msg})

    return errors, warnings


def parse_lint_xml(lint_xml_path):
    """
    Parse Android lint XML report.
    Returns (errors, warnings).
    """
    errors = []
    warnings = []

    if not lint_xml_path or not os.path.exists(lint_xml_path):
        return errors, warnings

    try:
        tree = ET.parse(lint_xml_path)
        root = tree.getroot()

        seen = set()
        for issue in root.findall("issue"):
            severity = issue.get("severity", "").lower()
            issue_id = issue.get("id", "")
            message = issue.get("message", "")[:120]

            location = issue.find("location")
            if location is not None:
                filepath = location.get("file", "-")
                parts = filepath.replace("\\", "/").split("/")
                short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
                line = location.get("line", "-")
            else:
                short_path = "-"
                line = "-"

            key = (short_path, line, issue_id)
            if key in seen:
                continue
            seen.add(key)

            entry = {
                "file": short_path,
                "line": line,
                "col": "-",
                "msg": f"{issue_id}: {message}",
            }

            if severity in ("error", "fatal"):
                errors.append(entry)
            elif severity == "warning":
                warnings.append(entry)

    except ET.ParseError as e:
        print(f"Warning: Could not parse lint XML ({e})")

    return errors, warnings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(build_errors, build_warnings, lint_errors, lint_warnings,
                build_rc, lint_rc, raw_output=None):
    """Print results in the pipeline contract format."""
    all_errors = build_errors + lint_errors
    all_warnings = build_warnings + lint_warnings
    failed = build_rc != 0

    if not failed and not all_errors:
        print(f"\nBUILD SUCCEEDED  |  {len(all_warnings)} warning(s)")
        return

    if failed and not all_errors:
        print(f"\nBUILD FAILED  |  0 error(s)  |  {len(all_warnings)} warning(s)\n")
        print("No parseable errors found. Showing relevant build output:\n")
        if raw_output:
            lines = raw_output.strip().splitlines()
            filtered = [
                l for l in lines
                if l.strip()
                and not any(skip in l for skip in [
                    "Downloading", "Download ", "> Task",
                    "BUILD SUCCESSFUL", "actionable task",
                ])
            ]
            problem_lines = [
                l for l in filtered
                if any(kw in l.lower() for kw in [
                    "error", "failed", "fatal", "cannot find",
                    "not found", "unresolved", "exception",
                ])
            ]
            if problem_lines:
                print("\n".join(problem_lines[:30]))
            else:
                print("\n".join(filtered[-30:]))
        sys.exit(1)

    error_count = len(all_errors)
    warning_count = len(all_warnings)
    print(f"\nBUILD FAILED  |  {error_count} error(s)  |  {warning_count} warning(s)\n")

    if build_errors:
        print("Compilation Errors:")
        _print_error_rows(build_errors)
        print()

    if lint_errors:
        print("Lint Errors:")
        _print_error_rows(lint_errors)
        print()


def _print_error_rows(errors):
    """Print a formatted error table."""
    fw = max(len(e["file"]) for e in errors)
    lw = max(len(str(e["line"])) for e in errors)

    header = f"  {'File':<{fw}}  {'Ln':>{lw}}  {'Error'}"
    print(header)
    print("  " + "-" * min(len(header) + 80, 120))

    for e in errors:
        print(f"  {e['file']:<{fw}}  {str(e['line']):>{lw}}  {e['msg']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run Android build (assemble + lint) and output errors in a minimal table."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--module", default="app", help="Gradle module name (default: app)")
    parser.add_argument("--variant", default="debug", help="Build variant (default: debug)")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    print(f"Building in: {project_dir}")

    gradlew = find_gradlew(project_dir)
    print(f"Gradle wrapper: {gradlew}")
    print(f"Module: {args.module}")
    print(f"Variant: {args.variant}")

    # Step 1: Assemble
    build_output, build_rc = run_assemble(project_dir, gradlew, args.module, args.variant)
    build_errors, build_warnings = parse_gradle_errors(build_output)

    if build_rc != 0:
        print(f"Assemble: FAILED ({len(build_errors)} error(s))")
    else:
        print(f"Assemble: OK ({len(build_warnings)} warning(s))")

    # Step 2: Lint (only if assemble succeeded)
    lint_output = ""
    lint_rc = 0
    lint_errors = []
    lint_warnings = []

    if build_rc == 0:
        lint_output, lint_rc, lint_xml = run_lint(
            project_dir, gradlew, args.module, args.variant
        )
        lint_errors, lint_warnings = parse_lint_xml(lint_xml)

        if lint_errors:
            print(f"Lint: {len(lint_errors)} error(s), {len(lint_warnings)} warning(s)")
        else:
            print(f"Lint: OK ({len(lint_warnings)} warning(s))")

    combined_output = (build_output + "\n" + lint_output).strip()

    print_table(
        build_errors, build_warnings,
        lint_errors, lint_warnings,
        build_rc, lint_rc,
        raw_output=combined_output,
    )

    if build_rc != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
