#!/usr/bin/env python3
"""
Run Bicep linting and compilation, output results in pipeline contract format.

Usage:
  python build.py [--project-dir /path/to/project] [--scheme <lint|build|all>] [--verbose]

The script auto-detects .bicep files and bicepconfig.json, then runs bicep lint/build.
Output format:
  BUILD SUCCEEDED | N warning(s)
  BUILD FAILED | N error(s) | N warning(s)
"""

import subprocess
import sys
import re
import argparse
import os
import shutil


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def detect_project_config(project_dir):
    """Detect Bicep project structure and configuration."""
    info = {
        "has_bicepconfig": False,
        "bicep_files": [],
        "has_modules_dir": False,
        "has_param_files": False,
        "bicep_available": False,
        "az_available": False,
    }

    info["has_bicepconfig"] = os.path.exists(
        os.path.join(project_dir, "bicepconfig.json")
    )
    info["has_modules_dir"] = os.path.isdir(
        os.path.join(project_dir, "modules")
    )

    # Find all .bicep files
    for root, dirs, files in os.walk(project_dir):
        # Skip hidden dirs and common non-source dirs
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d not in ("node_modules", "__pycache__", ".bicep",
                          "out", "dist", "build", "generated", "bin", "obj")
        ]
        for f in files:
            if f.endswith(".bicep"):
                rel = os.path.relpath(os.path.join(root, f), project_dir)
                info["bicep_files"].append(rel)

    # Check for parameter files
    for f in os.listdir(project_dir):
        if f.endswith(".bicepparam") or f.endswith(".parameters.json"):
            info["has_param_files"] = True
            break

    # Check tool availability
    info["bicep_available"] = find_tool("bicep") or find_tool("az")
    info["az_available"] = find_tool("az")

    return info


def find_tool(name):
    """Check if a tool is available on PATH."""
    return shutil.which(name) is not None


def find_bicep_command():
    """Determine the bicep CLI command to use (standalone or via az)."""
    if find_tool("bicep"):
        return ["bicep"]
    if find_tool("az"):
        return ["az", "bicep"]
    return None


# ---------------------------------------------------------------------------
# Tool runners
# ---------------------------------------------------------------------------

def run_bicep_build(project_dir, bicep_files, bicep_cmd):
    """Compile .bicep files to ARM JSON and return (output, errors, warnings)."""
    errors = []
    warnings = []
    all_output = []

    for bicep_file in bicep_files:
        # `az bicep build` requires --file; standalone `bicep build` takes positional.
        if bicep_cmd[0] == "az":
            cmd = bicep_cmd + ["build", "--file", bicep_file]
        else:
            cmd = bicep_cmd + ["build", bicep_file]
        print(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True, check=False
        )
        output = result.stdout + result.stderr
        all_output.append(output)

        parsed_errors, parsed_warnings = parse_bicep_diagnostics(
            output, bicep_file
        )
        errors.extend(parsed_errors)
        warnings.extend(parsed_warnings)

        # Non-zero exit with no parsed errors means a general failure
        if result.returncode != 0 and not parsed_errors:
            errors.append({
                "file": bicep_file,
                "line": "-",
                "msg": f"[bicep build] Compilation failed (exit code {result.returncode})",
            })

    return "\n".join(all_output), errors, warnings


def run_bicep_lint(project_dir, bicep_files, bicep_cmd):
    """Run bicep linter and return (output, errors, warnings).

    Note: The standalone `bicep` CLI does not have a separate `lint` subcommand.
    Linting is performed via `bicep build` when `bicepconfig.json` is present.
    The `az bicep lint` subcommand is available in recent az CLI versions.
    This function tries `az bicep lint` first, and falls back to `bicep build`
    (which includes lint diagnostics from bicepconfig.json rules).
    """
    errors = []
    warnings = []
    all_output = []

    # Determine lint command: only `az bicep lint` is a real subcommand
    use_az_lint = bicep_cmd[0] == "az"

    for bicep_file in bicep_files:
        if use_az_lint:
            cmd = ["az", "bicep", "lint", "--file", bicep_file]
        else:
            # Standalone bicep CLI: lint happens during build via bicepconfig.json
            cmd = bicep_cmd + ["build", bicep_file, "--stdout"]
        print(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True, check=False
        )
        output = result.stdout + result.stderr
        all_output.append(output)

        parsed_errors, parsed_warnings = parse_bicep_diagnostics(
            output, bicep_file
        )
        errors.extend(parsed_errors)
        warnings.extend(parsed_warnings)

    return "\n".join(all_output), errors, warnings


def parse_bicep_diagnostics(output, default_file):
    """
    Parse Bicep CLI diagnostic output.

    Bicep outputs diagnostics in the format:
      path/to/file.bicep(line,col) : severity code: message
    or:
      /path/to/file.bicep(line,col) : error BCP001: message
      /path/to/file.bicep(line,col) : warning no-unused-params: message
    """
    errors = []
    warnings = []

    # Pattern: file(line,col) : severity code: message
    pattern = re.compile(
        r"^(.+?)\((\d+),\d+\)\s*:\s*(error|warning|info)\s+(\S+)\s*:\s*(.+)$",
        re.MULTILINE,
    )

    seen = set()
    for m in pattern.finditer(output):
        filepath, line, severity, code, message = m.groups()
        # Shorten path
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, message)
        if key in seen:
            continue
        seen.add(key)

        entry = {
            "file": short_path,
            "line": line,
            "msg": f"[{code}] {message}",
        }
        if severity == "error":
            errors.append(entry)
        elif severity == "warning":
            warnings.append(entry)
        # info diagnostics are skipped

    return errors, warnings


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_table(all_errors, all_warnings, has_failures):
    """Print results in pipeline contract format."""
    if not has_failures and not all_errors:
        print(f"\nBUILD SUCCEEDED  |  {len(all_warnings)} warning(s)")
        if all_warnings:
            print_entries(all_warnings, "Warning")
        return

    print(
        f"\nBUILD FAILED  |  {len(all_errors)} error(s)  |  "
        f"{len(all_warnings)} warning(s)\n"
    )

    if not all_errors:
        print("No parseable errors found. A tool returned a non-zero exit code.")
        print("Run the tool manually for full output.")
        return

    print_entries(all_errors, "Error")


def print_entries(entries, label):
    """Print a formatted table of error/warning entries."""
    if not entries:
        return

    fw = max(len(e["file"]) for e in entries)
    lw = max(len(str(e["line"])) for e in entries)

    header = f"{'File':<{fw}}  {'Ln':>{lw}}  {label}"
    print(header)
    print("-" * min(len(header) + 80, 140))

    for e in entries:
        print(f"{e['file']:<{fw}}  {str(e['line']):>{lw}}  {e['msg']}")

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run Bicep linting and compilation in pipeline contract format."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument(
        "--scheme",
        default="all",
        choices=["lint", "build", "all"],
        help="Which checks to run (default: all)",
    )
    parser.add_argument("--verbose", action="store_true", help="Show full tool output")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    print(f"Building in: {project_dir}")

    if not os.path.isdir(project_dir):
        print(f"ERROR: Project directory does not exist: {project_dir}")
        sys.exit(1)

    info = detect_project_config(project_dir)

    if not info["bicep_files"]:
        print("WARNING: No .bicep files found in project.")
        print("\nBUILD SUCCEEDED  |  0 warning(s)")
        sys.exit(0)

    print(f"Bicep files: {len(info['bicep_files'])}")
    if info["has_bicepconfig"]:
        print("Config:      bicepconfig.json found")
    if info["has_modules_dir"]:
        print("Modules:     modules/ directory found")

    bicep_cmd = find_bicep_command()
    if not bicep_cmd:
        print("ERROR: Neither 'bicep' nor 'az' CLI found on PATH.")
        print("Install the Bicep CLI: https://learn.microsoft.com/azure/azure-resource-manager/bicep/install")
        print("\nBUILD FAILED  |  1 error(s)  |  0 warning(s)\n")
        print("File  Ln  Error")
        print("-" * 80)
        print("-     -   [setup] Bicep CLI not found on PATH")
        sys.exit(1)

    all_errors = []
    all_warnings = []
    has_failures = False

    # Determine which steps to run
    steps = []
    if args.scheme in ("lint", "all"):
        steps.append("lint")
    if args.scheme in ("build", "all"):
        steps.append("build")

    for step in steps:
        print(f"\n--- Running: bicep {step} ---")

        if step == "lint":
            output, errors, warnings = run_bicep_lint(
                project_dir, info["bicep_files"], bicep_cmd
            )
        else:
            output, errors, warnings = run_bicep_build(
                project_dir, info["bicep_files"], bicep_cmd
            )

        if args.verbose:
            print(output)

        all_errors.extend(errors)
        all_warnings.extend(warnings)
        if errors:
            has_failures = True

    print_table(all_errors, all_warnings, has_failures)

    if has_failures or all_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
