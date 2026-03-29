#!/usr/bin/env python3
"""
Run Python type checking and linting, output results in pipeline contract format.

Usage:
  python build.py [--project-dir /path/to/project] [--scheme <mypy|pyright|ruff|flake8|all>] [--configuration <strict|relaxed>]

The script auto-detects which tools are configured in pyproject.toml/setup.cfg and runs them.
Output format:
  BUILD SUCCEEDED | N warning(s)
  BUILD FAILED | N error(s) | N warning(s)
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

def detect_project_type(project_dir):
    """Detect Python project type and available tools from config files."""
    info = {
        "has_pyproject": False,
        "has_setup_py": False,
        "has_setup_cfg": False,
        "has_requirements": False,
        "mypy_configured": False,
        "pyright_configured": False,
        "ruff_configured": False,
        "flake8_configured": False,
        "package_manager": "pip",
    }

    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    setup_cfg_path = os.path.join(project_dir, "setup.cfg")
    setup_py_path = os.path.join(project_dir, "setup.py")
    requirements_path = os.path.join(project_dir, "requirements.txt")

    info["has_setup_py"] = os.path.exists(setup_py_path)
    info["has_setup_cfg"] = os.path.exists(setup_cfg_path)
    info["has_requirements"] = os.path.exists(requirements_path)

    if os.path.exists(pyproject_path):
        info["has_pyproject"] = True
        try:
            with open(pyproject_path, "r") as f:
                content = f.read()

            # Detect package manager
            if "[tool.poetry" in content:
                info["package_manager"] = "poetry"
            elif "[tool.pdm" in content:
                info["package_manager"] = "pdm"
            elif "[tool.uv" in content or "[project]" in content:
                # uv uses standard pyproject.toml [project] table
                info["package_manager"] = "uv"

            # Detect configured tools
            info["mypy_configured"] = "[tool.mypy]" in content or "[mypy]" in content
            info["ruff_configured"] = "[tool.ruff" in content
            info["pyright_configured"] = (
                "[tool.pyright]" in content
                or os.path.exists(os.path.join(project_dir, "pyrightconfig.json"))
            )

        except Exception:
            pass

    # Check setup.cfg for tool configs
    if os.path.exists(setup_cfg_path):
        try:
            with open(setup_cfg_path, "r") as f:
                cfg_content = f.read()
            if "[mypy]" in cfg_content:
                info["mypy_configured"] = True
            if "[flake8]" in cfg_content:
                info["flake8_configured"] = True
        except Exception:
            pass

    # Check for standalone config files
    if os.path.exists(os.path.join(project_dir, "mypy.ini")):
        info["mypy_configured"] = True
    if os.path.exists(os.path.join(project_dir, ".mypy.ini")):
        info["mypy_configured"] = True
    if os.path.exists(os.path.join(project_dir, "pyrightconfig.json")):
        info["pyright_configured"] = True
    if os.path.exists(os.path.join(project_dir, ".flake8")):
        info["flake8_configured"] = True
    if os.path.exists(os.path.join(project_dir, "ruff.toml")):
        info["ruff_configured"] = True
    if os.path.exists(os.path.join(project_dir, ".ruff.toml")):
        info["ruff_configured"] = True

    return info


def find_tool(name):
    """Check if a tool is available on PATH."""
    try:
        result = subprocess.run(
            ["which", name], capture_output=True, text=True, check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def find_source_dirs(project_dir):
    """Find the source directories to check."""
    candidates = ["src", "app", "lib"]
    for c in candidates:
        if os.path.isdir(os.path.join(project_dir, c)):
            return [c]

    # Look for Python packages (directories with __init__.py)
    packages = []
    for entry in os.listdir(project_dir):
        full = os.path.join(project_dir, entry)
        if (
            os.path.isdir(full)
            and not entry.startswith(".")
            and not entry.startswith("_")
            and entry not in ("tests", "test", "docs", "scripts", "migrations", "venv", "env", ".venv", "node_modules", "__pycache__")
            and os.path.exists(os.path.join(full, "__init__.py"))
        ):
            packages.append(entry)

    return packages if packages else ["."]


# ---------------------------------------------------------------------------
# Tool runners
# ---------------------------------------------------------------------------

def run_mypy(project_dir, source_dirs, strict=False):
    """Run mypy type checker and return (output, errors, warnings)."""
    cmd = ["python3", "-m", "mypy"]
    if strict:
        cmd.append("--strict")
    cmd.extend(source_dirs)

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )
    output = result.stdout + result.stderr
    errors = []
    warnings = []

    # mypy format: path/to/file.py:10: error: Message [error-code]
    pattern = re.compile(
        r"^(.+?):(\d+):\s+(error|warning|note):\s+(.+)$", re.MULTILINE
    )
    seen = set()
    for m in pattern.finditer(output):
        filepath, line, severity, message = m.groups()
        # Shorten path
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        message = message.strip()[:120]
        key = (short_path, line, message)
        if key in seen:
            continue
        seen.add(key)

        entry = {"file": short_path, "line": line, "msg": f"[mypy] {message}"}
        if severity == "error":
            errors.append(entry)
        elif severity == "warning":
            warnings.append(entry)
        # notes are informational, skip

    # Check for summary line with error count
    summary_match = re.search(r"Found (\d+) errors? in", output)
    if summary_match and not errors:
        # mypy reported errors but we didn't parse them — treat as a single error
        errors.append({
            "file": "-",
            "line": "-",
            "msg": f"[mypy] {summary_match.group(0).strip()}"
        })

    return output, errors, warnings


def run_pyright(project_dir, source_dirs):
    """Run pyright type checker and return (output, errors, warnings)."""
    cmd = ["pyright", "--outputjson"]
    cmd.extend(source_dirs)

    print(f"Running: pyright {' '.join(source_dirs)}")
    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )

    errors = []
    warnings = []

    try:
        data = json.loads(result.stdout)
        for diag in data.get("generalDiagnostics", []):
            filepath = diag.get("file", "-")
            parts = filepath.replace("\\", "/").split("/")
            short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
            line = str(diag.get("range", {}).get("start", {}).get("line", 0) + 1)
            message = diag.get("message", "").strip()[:120]
            severity = diag.get("severity", "error")
            rule = diag.get("rule", "")
            msg_text = f"[pyright:{rule}] {message}" if rule else f"[pyright] {message}"

            entry = {"file": short_path, "line": line, "msg": msg_text}
            if severity == "error":
                errors.append(entry)
            elif severity == "warning":
                warnings.append(entry)
    except (json.JSONDecodeError, KeyError):
        # Fall back to text parsing
        output = result.stdout + result.stderr
        pattern = re.compile(
            r"^(.+?):(\d+):\d+\s+-\s+(error|warning):\s+(.+)$", re.MULTILINE
        )
        for m in pattern.finditer(output):
            filepath, line, severity, message = m.groups()
            parts = filepath.replace("\\", "/").split("/")
            short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
            entry = {"file": short_path, "line": line, "msg": f"[pyright] {message.strip()[:120]}"}
            if severity == "error":
                errors.append(entry)
            else:
                warnings.append(entry)

    return result.stdout + result.stderr, errors, warnings


def run_ruff(project_dir, source_dirs):
    """Run ruff linter and return (output, errors, warnings)."""
    cmd = ["ruff", "check", "--output-format=json"]
    cmd.extend(source_dirs)

    print(f"Running: ruff check {' '.join(source_dirs)}")
    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )

    errors = []
    warnings = []

    try:
        diagnostics = json.loads(result.stdout)
        for diag in diagnostics:
            filepath = diag.get("filename", "-")
            parts = filepath.replace("\\", "/").split("/")
            short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
            line = str(diag.get("location", {}).get("row", 0))
            code = diag.get("code", "")
            message = diag.get("message", "").strip()[:120]
            msg_text = f"[ruff:{code}] {message}" if code else f"[ruff] {message}"

            entry = {"file": short_path, "line": line, "msg": msg_text}

            # E and W prefixes: E=error, W=warning; F=pyflakes (error); others vary
            if code and code[0] in ("W", "D"):
                warnings.append(entry)
            else:
                errors.append(entry)
    except (json.JSONDecodeError, KeyError):
        # Fall back to text parsing
        # ruff text format: path/to/file.py:10:5: E123 message
        output = result.stdout + result.stderr
        pattern = re.compile(
            r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$", re.MULTILINE
        )
        for m in pattern.finditer(output):
            filepath, line, col, code, message = m.groups()
            parts = filepath.replace("\\", "/").split("/")
            short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
            entry = {"file": short_path, "line": line, "msg": f"[ruff:{code}] {message.strip()[:120]}"}
            if code[0] in ("W", "D"):
                warnings.append(entry)
            else:
                errors.append(entry)

    return result.stdout + result.stderr, errors, warnings


def run_flake8(project_dir, source_dirs):
    """Run flake8 linter and return (output, errors, warnings)."""
    cmd = ["python3", "-m", "flake8", "--format=default"]
    cmd.extend(source_dirs)

    print(f"Running: flake8 {' '.join(source_dirs)}")
    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )

    output = result.stdout + result.stderr
    errors = []
    warnings = []

    # flake8 format: path/to/file.py:10:5: E123 message
    pattern = re.compile(
        r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$", re.MULTILINE
    )
    for m in pattern.finditer(output):
        filepath, line, col, code, message = m.groups()
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-3:]) if len(parts) > 3 else filepath
        entry = {"file": short_path, "line": line, "msg": f"[flake8:{code}] {message.strip()[:120]}"}
        if code[0] == "W":
            warnings.append(entry)
        else:
            errors.append(entry)

    return output, errors, warnings


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

    print(f"\nBUILD FAILED  |  {len(all_errors)} error(s)  |  {len(all_warnings)} warning(s)\n")

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
        description="Run Python type checking and linting in pipeline contract format."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument(
        "--scheme",
        default=None,
        help="Specific tool to run: mypy, pyright, ruff, flake8, or all (default: auto-detect)"
    )
    parser.add_argument(
        "--configuration",
        default="strict",
        choices=["strict", "relaxed"],
        help="Configuration level (strict enables --strict for mypy)"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    print(f"Building in: {project_dir}")

    if not os.path.isdir(project_dir):
        print(f"ERROR: Project directory does not exist: {project_dir}")
        sys.exit(1)

    info = detect_project_type(project_dir)
    print(f"Package manager: {info['package_manager']}")

    source_dirs = find_source_dirs(project_dir)
    print(f"Source directories: {source_dirs}")

    # Determine which tools to run
    tools_to_run = []
    if args.scheme:
        scheme = args.scheme.lower()
        if scheme == "all":
            tools_to_run = ["typecheck", "lint"]
        elif scheme in ("mypy", "pyright"):
            tools_to_run = [scheme]
        elif scheme in ("ruff", "flake8"):
            tools_to_run = [scheme]
        else:
            print(f"WARNING: Unknown scheme '{args.scheme}'. Running auto-detection.")
            tools_to_run = []

    if not tools_to_run:
        # Auto-detect: run whatever is configured
        if info["mypy_configured"] or info["pyright_configured"]:
            tools_to_run.append("typecheck")
        if info["ruff_configured"]:
            tools_to_run.append("ruff")
        elif info["flake8_configured"]:
            tools_to_run.append("flake8")

        # If nothing is configured, try to run what's available
        if not tools_to_run:
            if find_tool("ruff"):
                tools_to_run.append("ruff")
            if find_tool("mypy") or find_tool("python3"):
                tools_to_run.append("typecheck")
            if not tools_to_run:
                print("WARNING: No type checker or linter configured or available.")
                print("Configure mypy, pyright, or ruff in pyproject.toml.")
                print("\nBUILD SUCCEEDED  |  0 warning(s)")
                sys.exit(0)

    all_errors = []
    all_warnings = []
    has_failures = False
    strict = args.configuration == "strict"

    for tool in tools_to_run:
        print(f"\n--- Running: {tool} ---")

        if tool == "typecheck":
            if args.scheme and args.scheme.lower() == "pyright":
                if find_tool("pyright"):
                    output, errors, warnings = run_pyright(project_dir, source_dirs)
                else:
                    print("ERROR: pyright not found on PATH.")
                    has_failures = True
                    continue
            elif args.scheme and args.scheme.lower() == "mypy":
                output, errors, warnings = run_mypy(project_dir, source_dirs, strict=strict)
            elif info["mypy_configured"]:
                output, errors, warnings = run_mypy(project_dir, source_dirs, strict=strict)
            elif info["pyright_configured"] and find_tool("pyright"):
                output, errors, warnings = run_pyright(project_dir, source_dirs)
            else:
                # Default to mypy
                output, errors, warnings = run_mypy(project_dir, source_dirs, strict=strict)

            all_errors.extend(errors)
            all_warnings.extend(warnings)
            if errors:
                has_failures = True

        elif tool == "ruff":
            output, errors, warnings = run_ruff(project_dir, source_dirs)
            all_errors.extend(errors)
            all_warnings.extend(warnings)
            if errors:
                has_failures = True

        elif tool == "flake8":
            output, errors, warnings = run_flake8(project_dir, source_dirs)
            all_errors.extend(errors)
            all_warnings.extend(warnings)
            if errors:
                has_failures = True

        elif tool == "lint":
            # "all" scheme: run ruff or flake8
            if info["ruff_configured"] or find_tool("ruff"):
                output, errors, warnings = run_ruff(project_dir, source_dirs)
            elif info["flake8_configured"]:
                output, errors, warnings = run_flake8(project_dir, source_dirs)
            else:
                print("No linter configured or available. Skipping lint step.")
                continue
            all_errors.extend(errors)
            all_warnings.extend(warnings)
            if errors:
                has_failures = True

    print_table(all_errors, all_warnings, has_failures)

    if has_failures or all_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
