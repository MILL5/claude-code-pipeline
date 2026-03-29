#!/usr/bin/env python3
"""
Run React/TypeScript build and output errors in a minimal table.
Usage: python build.py [--project-dir /path/to/project] [--scheme build-script] [--configuration dev|production]
"""

import subprocess
import sys
import re
import argparse
import os
import json


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
    return "npm"  # Default fallback


def pm_run_cmd(pm, script_name):
    """Return the command list to run a package.json script with the given PM."""
    if pm == "npm":
        return ["npm", "run", script_name]
    elif pm == "yarn":
        return ["yarn", script_name]
    elif pm == "pnpm":
        return ["pnpm", "run", script_name]
    elif pm == "bun":
        return ["bun", "run", script_name]
    return ["npm", "run", script_name]


# ---------------------------------------------------------------------------
# Build steps
# ---------------------------------------------------------------------------

def run_typecheck(project_dir, pm):
    """
    Run TypeScript type-checking (tsc --noEmit) if tsconfig.json exists.
    Returns (stdout+stderr, returncode).
    """
    tsconfig = os.path.join(project_dir, "tsconfig.json")
    if not os.path.exists(tsconfig):
        return "", 0

    print("Running TypeScript type-check...")

    # Use npx/pnpm dlx/yarn/bunx to ensure tsc is found
    if pm == "pnpm":
        cmd = ["pnpm", "exec", "tsc", "--noEmit"]
    elif pm == "yarn":
        cmd = ["yarn", "tsc", "--noEmit"]
    elif pm == "bun":
        cmd = ["bun", "run", "tsc", "--noEmit"]
    else:
        cmd = ["npx", "tsc", "--noEmit"]

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.stdout + result.stderr, result.returncode


def run_build(project_dir, pm, scheme=None, configuration=None):
    """
    Run the build script from package.json.
    Returns (stdout+stderr, returncode).
    """
    # Read package.json to find available scripts
    pkg_path = os.path.join(project_dir, "package.json")
    if not os.path.exists(pkg_path):
        print("ERROR: No package.json found in:")
        print(f"  {os.path.abspath(project_dir)}")
        sys.exit(1)

    with open(pkg_path) as f:
        pkg = json.load(f)

    scripts = pkg.get("scripts", {})

    # Determine which script to run
    if scheme and scheme in scripts:
        script_name = scheme
    elif "build" in scripts:
        script_name = "build"
    else:
        print("ERROR: No 'build' script found in package.json.")
        print(f"Available scripts: {', '.join(scripts.keys())}")
        sys.exit(1)

    cmd = pm_run_cmd(pm, script_name)

    # Set NODE_ENV for production builds
    env = os.environ.copy()
    if configuration == "production":
        env["NODE_ENV"] = "production"
    elif configuration == "dev":
        env["NODE_ENV"] = "development"

    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    return result.stdout + result.stderr, result.returncode


# ---------------------------------------------------------------------------
# Error parsing
# ---------------------------------------------------------------------------

def parse_typescript_errors(output):
    """
    Parse TypeScript compiler errors from tsc output.
    Format: path/to/file.ts(line,col): error TSxxxx: message
    Also handles: path/to/file.ts:line:col - error TSxxxx: message
    """
    errors = []
    warnings = []
    seen = set()

    # Format 1: file.ts(line,col): error TSxxxx: message
    pattern1 = re.compile(
        r"([^\s(]+\.(?:ts|tsx|js|jsx))\((\d+),(\d+)\):\s+(error|warning)\s+(TS\d+):\s+(.+)"
    )
    # Format 2: file.ts:line:col - error TSxxxx: message
    pattern2 = re.compile(
        r"([^\s:]+\.(?:ts|tsx|js|jsx)):(\d+):(\d+)\s+-\s+(error|warning)\s+(TS\d+):\s+(.+)"
    )

    for pattern in [pattern1, pattern2]:
        for m in pattern.finditer(output):
            filepath, line, col, severity, code, message = m.groups()
            # Shorten path for display
            parts = filepath.replace("\\", "/").split("/")
            short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
            message = message.strip()[:120]
            key = (short_path, line, code)
            if key in seen:
                continue
            seen.add(key)

            entry = {
                "file": short_path,
                "line": line,
                "col": col,
                "msg": f"{code}: {message}",
            }
            if severity == "error":
                errors.append(entry)
            else:
                warnings.append(entry)

    return errors, warnings


def parse_build_errors(output):
    """
    Parse common build tool errors (webpack, vite, esbuild, etc.).
    """
    errors = []
    warnings = []
    seen = set()

    # Webpack/Vite error format: ERROR in ./src/file.tsx line:col
    webpack_pattern = re.compile(
        r"ERROR in ([^\s]+\.(?:ts|tsx|js|jsx))\s+(\d+):(\d+)(?:-\d+)?\s*\n\s*(.+?)(?:\n|$)"
    )
    for m in webpack_pattern.finditer(output):
        filepath, line, col, message = m.groups()
        parts = filepath.replace("\\", "/").replace("./", "").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, message)
        if key not in seen:
            seen.add(key)
            errors.append({"file": short_path, "line": line, "col": col, "msg": message})

    # Vite/esbuild error: [ERROR] message \n  file:line:col
    vite_pattern = re.compile(
        r"\[ERROR\]\s+(.+?)\n\s+([^\s]+\.(?:ts|tsx|js|jsx)):(\d+):(\d+)"
    )
    for m in vite_pattern.finditer(output):
        message, filepath, line, col = m.groups()
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, message)
        if key not in seen:
            seen.add(key)
            errors.append({"file": short_path, "line": line, "col": col, "msg": message})

    # Generic "Error:" or "error:" lines as fallback
    generic_pattern = re.compile(
        r"^(?:Error|error|ERROR):\s+(.+)$", re.MULTILINE
    )
    for m in generic_pattern.finditer(output):
        msg = m.group(1).strip()[:120]
        key = ("-", "-", msg)
        if key not in seen:
            seen.add(key)
            errors.append({"file": "-", "line": "-", "col": "-", "msg": msg})

    # Warning lines
    warn_pattern = re.compile(
        r"^(?:Warning|warning|WARN):\s+(.+)$", re.MULTILINE
    )
    for m in warn_pattern.finditer(output):
        msg = m.group(1).strip()[:120]
        key = ("-", "-", msg)
        if key not in seen:
            seen.add(key)
            warnings.append({"file": "-", "line": "-", "col": "-", "msg": msg})

    return errors, warnings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(ts_errors, ts_warnings, build_errors, build_warnings, ts_rc, build_rc, raw_output=None):
    """Print results in the pipeline contract format."""
    all_errors = ts_errors + build_errors
    all_warnings = ts_warnings + build_warnings
    failed = ts_rc != 0 or build_rc != 0

    if not failed and not all_errors:
        print(f"\nBUILD SUCCEEDED  |  {len(all_warnings)} warning(s)")
        return

    if failed and not all_errors:
        # Build failed but we couldn't parse specific errors
        print(f"\nBUILD FAILED  |  0 error(s)  |  {len(all_warnings)} warning(s)\n")
        print("No parseable errors found. Showing relevant build output:\n")
        if raw_output:
            lines = raw_output.strip().splitlines()
            # Filter noise
            filtered = [
                l for l in lines
                if not any(skip in l for skip in [
                    "node_modules/", "at Object.", "at Module.",
                    "at async", "  at ", "    at "
                ])
                and l.strip()
            ]
            problem_lines = [
                l for l in filtered
                if any(kw in l.lower() for kw in [
                    "error", "failed", "fatal", "cannot find",
                    "module not found", "syntaxerror", "unexpected token"
                ])
            ]
            if problem_lines:
                print("\n".join(problem_lines[:30]))
            else:
                print("\n".join(filtered[-30:]))
        sys.exit(1)

    print(f"\nBUILD FAILED  |  {len(all_errors)} error(s)  |  {len(all_warnings)} warning(s)\n")

    if ts_errors:
        print("TypeScript Errors:")
        _print_error_rows(ts_errors)
        print()

    if build_errors:
        print("Build Errors:")
        _print_error_rows(build_errors)
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
        description="Run React/TypeScript build and output errors in a minimal table."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--scheme", default=None, help="Build script name from package.json (default: 'build')")
    parser.add_argument("--configuration", default=None, help="Build configuration: dev or production")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    print(f"Building in: {project_dir}")

    pm = detect_package_manager(project_dir)
    print(f"Package manager: {pm}")

    # Step 1: TypeScript type-check
    ts_output, ts_rc = run_typecheck(project_dir, pm)
    ts_errors, ts_warnings = parse_typescript_errors(ts_output)

    if ts_rc != 0:
        print(f"TypeScript check: FAILED ({len(ts_errors)} error(s))")
    else:
        print("TypeScript check: OK")

    # Step 2: Run build script
    build_output, build_rc = run_build(project_dir, pm, args.scheme, args.configuration)
    build_errors, build_warnings = parse_build_errors(build_output)

    # Combine outputs for fallback display
    combined_output = (ts_output + "\n" + build_output).strip()

    print_table(
        ts_errors, ts_warnings,
        build_errors, build_warnings,
        ts_rc, build_rc,
        raw_output=combined_output,
    )

    if ts_rc != 0 or build_rc != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
