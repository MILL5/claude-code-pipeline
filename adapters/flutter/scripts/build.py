#!/usr/bin/env python3
"""
Run Flutter build (analyze + format check) and output errors in a minimal table.
Usage: python build.py [--project-dir /path/to/project] [--no-format-check]
"""

import subprocess
import sys
import re
import argparse
import os


# ---------------------------------------------------------------------------
# Flutter SDK detection
# ---------------------------------------------------------------------------

def find_flutter():
    """Find the flutter executable."""
    # Check if flutter is in PATH
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

    # Check for FVM
    fvm_path = os.path.join(".fvm", "flutter_sdk", "bin", "flutter")
    if os.path.exists(fvm_path):
        return [fvm_path]

    print("ERROR: Flutter SDK not found. Ensure 'flutter' is in PATH or FVM is configured.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Build steps
# ---------------------------------------------------------------------------

def run_analyze(project_dir, flutter_cmd):
    """
    Run flutter analyze.
    Returns (stdout+stderr, returncode).
    """
    print("Running flutter analyze...")
    cmd = flutter_cmd + ["analyze", "--no-pub"]

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.stdout + result.stderr, result.returncode


def run_format_check(project_dir, flutter_cmd):
    """
    Run dart format --set-exit-if-changed to check formatting.
    Returns (stdout+stderr, returncode).
    """
    print("Running dart format check...")

    # Use dart format from the Flutter SDK
    dart_cmd = flutter_cmd[:-1] + ["dart"] if flutter_cmd[-1] == "flutter" else ["dart"]
    cmd = dart_cmd + ["format", "--set-exit-if-changed", "--output=none", "lib/"]

    # Check if lib/ exists
    lib_dir = os.path.join(project_dir, "lib")
    if not os.path.isdir(lib_dir):
        return "No lib/ directory found, skipping format check.", 0

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout + result.stderr, result.returncode


# ---------------------------------------------------------------------------
# Error parsing
# ---------------------------------------------------------------------------

def parse_analyze_output(output):
    """
    Parse flutter analyze output.
    Format: severity - message - path/to/file.dart:line:col - rule_name
    Also: path/to/file.dart:line:col - message - rule_name
    """
    errors = []
    warnings = []
    infos = []
    seen = set()

    # Standard flutter analyze format:
    # severity • message • path:line:col • rule_name
    # Also handles: severity - message - path:line:col - rule_name
    pattern = re.compile(
        r"(error|warning|info)\s*[•\-]\s*(.+?)\s*[•\-]\s*([^\s]+\.dart):(\d+):(\d+)\s*[•\-]\s*(\S+)"
    )

    for m in pattern.finditer(output):
        severity, message, filepath, line, col, rule = m.groups()
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, rule)
        if key in seen:
            continue
        seen.add(key)

        entry = {
            "file": short_path,
            "line": line,
            "col": col,
            "msg": f"{rule}: {message}",
        }
        if severity == "error":
            errors.append(entry)
        elif severity == "warning":
            warnings.append(entry)
        else:
            infos.append(entry)

    # Fallback: compilation errors
    # file.dart:10:5: Error: message
    compile_pattern = re.compile(
        r"([^\s]+\.dart):(\d+):(\d+):\s+(Error|Warning):\s+(.+)"
    )
    for m in compile_pattern.finditer(output):
        filepath, line, col, severity, message = m.groups()
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, message)
        if key in seen:
            continue
        seen.add(key)

        entry = {"file": short_path, "line": line, "col": col, "msg": message}
        if severity == "Error":
            errors.append(entry)
        else:
            warnings.append(entry)

    return errors, warnings, infos


def parse_format_output(output):
    """
    Parse dart format --set-exit-if-changed output.
    Lists files that would be changed.
    """
    unformatted = []
    for line in output.strip().splitlines():
        line = line.strip()
        if line.endswith(".dart") and not line.startswith("Formatted"):
            parts = line.replace("\\", "/").split("/")
            short_path = "/".join(parts[-3:]) if len(parts) > 3 else line
            unformatted.append(short_path)
    return unformatted


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(analyze_errors, analyze_warnings, analyze_infos,
                format_issues, analyze_rc, format_rc, raw_output=None):
    """Print results in the pipeline contract format."""
    all_errors = analyze_errors + [
        {"file": f, "line": "-", "col": "-", "msg": "Needs formatting (dart format)"}
        for f in format_issues
    ]
    all_warnings = analyze_warnings
    failed = analyze_rc != 0 or format_rc != 0

    if not failed and not all_errors:
        warning_count = len(all_warnings) + len(analyze_infos)
        print(f"\nBUILD SUCCEEDED  |  {warning_count} warning(s)")
        return

    if failed and not all_errors:
        warning_count = len(all_warnings) + len(analyze_infos)
        print(f"\nBUILD FAILED  |  0 error(s)  |  {warning_count} warning(s)\n")
        print("No parseable errors found. Showing relevant build output:\n")
        if raw_output:
            lines = raw_output.strip().splitlines()
            filtered = [
                l for l in lines
                if l.strip()
                and not any(skip in l for skip in [
                    "Analyzing", "No issues found", "files analyzed",
                ])
            ]
            problem_lines = [
                l for l in filtered
                if any(kw in l.lower() for kw in [
                    "error", "failed", "fatal", "cannot",
                    "not found", "invalid", "unexpected",
                ])
            ]
            if problem_lines:
                print("\n".join(problem_lines[:30]))
            else:
                print("\n".join(filtered[-30:]))
        sys.exit(1)

    error_count = len(all_errors)
    warning_count = len(all_warnings) + len(analyze_infos)
    print(f"\nBUILD FAILED  |  {error_count} error(s)  |  {warning_count} warning(s)\n")

    if analyze_errors:
        print("Analysis Errors:")
        _print_error_rows(analyze_errors)
        print()

    if format_issues:
        print("Formatting Issues:")
        for f in format_issues[:20]:
            print(f"  {f}")
        if len(format_issues) > 20:
            print(f"  ... and {len(format_issues) - 20} more")
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
        description="Run Flutter build (analyze + format check) and output errors in a minimal table."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--no-format-check", action="store_true", help="Skip dart format check")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    print(f"Building in: {project_dir}")

    # Verify pubspec.yaml exists
    if not os.path.exists(os.path.join(project_dir, "pubspec.yaml")):
        print("ERROR: No pubspec.yaml found in:")
        print(f"  {project_dir}")
        sys.exit(1)

    flutter_cmd = find_flutter()
    print(f"Flutter: {' '.join(flutter_cmd)}")

    # Step 1: flutter analyze
    analyze_output, analyze_rc = run_analyze(project_dir, flutter_cmd)
    analyze_errors, analyze_warnings, analyze_infos = parse_analyze_output(analyze_output)

    if analyze_rc != 0:
        print(f"Analysis: FAILED ({len(analyze_errors)} error(s), {len(analyze_warnings)} warning(s))")
    else:
        print(f"Analysis: OK ({len(analyze_warnings)} warning(s), {len(analyze_infos)} info(s))")

    # Step 2: dart format check
    format_output = ""
    format_rc = 0
    format_issues = []

    if not args.no_format_check:
        format_output, format_rc = run_format_check(project_dir, flutter_cmd)
        format_issues = parse_format_output(format_output) if format_rc != 0 else []

        if format_rc != 0:
            print(f"Format check: FAILED ({len(format_issues)} file(s) need formatting)")
        else:
            print("Format check: OK")

    # Combine outputs for fallback display
    combined_output = (analyze_output + "\n" + format_output).strip()

    print_table(
        analyze_errors, analyze_warnings, analyze_infos,
        format_issues, analyze_rc, format_rc,
        raw_output=combined_output,
    )

    if analyze_rc != 0 or format_rc != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
