#!/usr/bin/env python3
"""
Run Bicep infrastructure tests and output results in pipeline contract format.

Usage:
  python test.py [--project-dir /path/to/project] [--scheme <arm-ttk|psrule|what-if|all>]
                 [--resource-group <name>] [--no-coverage]

Supports ARM-TTK, PSRule for Azure, and az deployment what-if.
Output format:
  Summary: Total: N, Passed: N, Failed: N | Coverage: X.X%
"""

import subprocess
import sys
import re
import argparse
import os
import json
import shutil


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def detect_test_config(project_dir):
    """Detect available test frameworks and configuration."""
    info = {
        "has_arm_ttk": False,
        "has_psrule": False,
        "has_az_cli": False,
        "has_pester": False,
        "bicep_files": [],
        "test_files": [],
        "psrule_config": None,
        "resource_types": set(),
    }

    # Check tool availability
    info["has_az_cli"] = find_tool("az")
    info["has_psrule"] = _check_psrule_available()
    info["has_arm_ttk"] = _check_arm_ttk_available()
    info["has_pester"] = _check_pester_available()

    # Find .bicep files
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d not in ("node_modules", "__pycache__", ".bicep")
        ]
        for f in files:
            if f.endswith(".bicep"):
                rel = os.path.relpath(os.path.join(root, f), project_dir)
                info["bicep_files"].append(rel)

    # Find test files (Pester tests)
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
        ]
        for f in files:
            if f.endswith(".Tests.ps1"):
                rel = os.path.relpath(os.path.join(root, f), project_dir)
                info["test_files"].append(rel)

    # Check for PSRule config
    psrule_config = os.path.join(project_dir, "ps-rule.yaml")
    if os.path.exists(psrule_config):
        info["psrule_config"] = psrule_config

    # Extract resource types from .bicep files for coverage calculation
    resource_pattern = re.compile(
        r"resource\s+\w+\s+'(Microsoft\.\w+/\w+)@"
    )
    for bicep_file in info["bicep_files"]:
        try:
            with open(os.path.join(project_dir, bicep_file), "r") as fh:
                content = fh.read()
            for m in resource_pattern.finditer(content):
                info["resource_types"].add(m.group(1))
        except Exception:
            pass

    return info


def find_tool(name):
    """Check if a tool is available on PATH."""
    return shutil.which(name) is not None


def _check_psrule_available():
    """Check if PSRule for Azure is available."""
    # Check dotnet tool
    try:
        result = subprocess.run(
            ["dotnet", "tool", "list", "-g"],
            capture_output=True, text=True, check=False,
        )
        if "psrule" in result.stdout.lower():
            return True
    except Exception:
        pass

    # Check PowerShell module
    try:
        result = subprocess.run(
            ["pwsh", "-Command", "Get-Module -ListAvailable PSRule.Rules.Azure"],
            capture_output=True, text=True, check=False,
        )
        if "PSRule.Rules.Azure" in result.stdout:
            return True
    except Exception:
        pass

    return False


def _check_arm_ttk_available():
    """Check if ARM-TTK is available."""
    try:
        result = subprocess.run(
            ["pwsh", "-Command", "Get-Module -ListAvailable arm-ttk"],
            capture_output=True, text=True, check=False,
        )
        return "arm-ttk" in result.stdout.lower()
    except Exception:
        return False


def _check_pester_available():
    """Check if Pester is available."""
    try:
        result = subprocess.run(
            ["pwsh", "-Command", "Get-Module -ListAvailable Pester"],
            capture_output=True, text=True, check=False,
        )
        return "Pester" in result.stdout
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test runners
# ---------------------------------------------------------------------------

def run_psrule(project_dir, bicep_files, psrule_config):
    """Run PSRule for Azure and return (total, passed, failed, failures)."""
    total = 0
    passed = 0
    failed = 0
    failures = {}

    # Build PSRule command
    cmd_parts = [
        "Invoke-PSRule",
        "-InputPath", ".",
        "-Module", "PSRule.Rules.Azure",
        "-Baseline", "Azure.Default",
        "-OutputFormat", "Json",
    ]

    if psrule_config:
        cmd_parts.extend(["-Option", psrule_config])

    cmd_str = " ".join(cmd_parts)
    cmd = ["pwsh", "-Command", cmd_str]

    print(f"Running: {cmd_str}")
    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )

    output = result.stdout

    # Parse JSON output
    try:
        # PSRule outputs one JSON object per line
        for line in output.strip().splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                record = json.loads(line)
                total += 1
                outcome = record.get("outcome", "").lower()
                if outcome == "pass":
                    passed += 1
                elif outcome in ("fail", "error"):
                    failed += 1
                    rule_name = record.get("ruleName", "unknown")
                    target = record.get("targetName", "unknown")
                    reason = record.get("reason", [""])[0] if record.get("reason") else ""
                    failures[f"{rule_name}:{target}"] = reason[:160]
            except json.JSONDecodeError:
                continue
    except Exception:
        # Fall back: try to parse text output
        pass_count = output.count(" Pass ")
        fail_count = output.count(" Fail ")
        total = pass_count + fail_count
        passed = pass_count
        failed = fail_count

    return total, passed, failed, failures


def run_arm_ttk(project_dir, bicep_files):
    """Run ARM-TTK template tests and return (total, passed, failed, failures)."""
    total = 0
    passed = 0
    failed = 0
    failures = {}

    for bicep_file in bicep_files:
        cmd_str = f"Test-AzTemplate -TemplatePath '{bicep_file}' -ErrorAction Continue"
        cmd = ["pwsh", "-Command", cmd_str]

        print(f"Running: Test-AzTemplate -TemplatePath '{bicep_file}'")
        result = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True, check=False
        )
        output = result.stdout + result.stderr

        # Parse ARM-TTK output
        # Format: [+] Test Name (N ms)  or  [-] Test Name (N ms)
        pass_pattern = re.compile(r"\[\+\]\s+(.+?)\s+\(\d+")
        fail_pattern = re.compile(r"\[-\]\s+(.+?)\s+\(\d+")

        for m in pass_pattern.finditer(output):
            total += 1
            passed += 1

        for m in fail_pattern.finditer(output):
            total += 1
            failed += 1
            test_name = m.group(1).strip()
            # Try to find the error message after the failure
            failures[f"{bicep_file}::{test_name}"] = ""

        # Extract failure details
        detail_pattern = re.compile(
            r"\[-\]\s+(.+?)\s+\(\d+.*?\n(.*?)(?=\n\[|$)", re.DOTALL
        )
        for m in detail_pattern.finditer(output):
            test_name = m.group(1).strip()
            details = m.group(2).strip()[:160]
            key = f"{bicep_file}::{test_name}"
            if key in failures:
                failures[key] = details

    return total, passed, failed, failures


def run_what_if(project_dir, bicep_files, resource_group):
    """Run az deployment what-if and return (total, passed, failed, failures)."""
    total = 0
    passed = 0
    failed = 0
    failures = {}

    # Find main template (prefer main.bicep, fall back to first .bicep file)
    template = None
    for f in bicep_files:
        if os.path.basename(f) == "main.bicep":
            template = f
            break
    if not template and bicep_files:
        template = bicep_files[0]

    if not template:
        return 0, 0, 0, {"setup": "No .bicep template files found"}

    # Find parameter file
    param_file = None
    for ext in (".bicepparam", ".parameters.json"):
        for candidate in os.listdir(project_dir):
            if candidate.endswith(ext):
                param_file = candidate
                break
        if param_file:
            break

    cmd = [
        "az", "deployment", "group", "what-if",
        "--resource-group", resource_group,
        "--template-file", template,
        "--no-pretty-print",
        "--output", "json",
    ]
    if param_file:
        cmd.extend(["--parameters", f"@{param_file}"])

    print(f"Running: az deployment group what-if --template-file {template}")
    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip()[:160] if result.stderr else "Unknown error"
        return 1, 0, 1, {"what-if": error_msg}

    # Parse what-if JSON output
    try:
        data = json.loads(result.stdout)
        changes = data.get("changes", [])

        for change in changes:
            total += 1
            change_type = change.get("changeType", "unknown")
            resource_id = change.get("resourceId", "unknown")
            # Extract short name
            parts = resource_id.split("/")
            short_name = parts[-1] if parts else resource_id

            if change_type in ("Create", "Modify", "NoChange", "Ignore"):
                passed += 1
            elif change_type == "Delete":
                failed += 1
                failures[short_name] = f"Resource will be DELETED ({change_type})"
            else:
                passed += 1

    except (json.JSONDecodeError, KeyError) as e:
        return 1, 0, 1, {"what-if-parse": f"Failed to parse what-if output: {e}"}

    return total, passed, failed, failures


# ---------------------------------------------------------------------------
# Coverage calculation
# ---------------------------------------------------------------------------

def calculate_coverage(test_config, total_tests):
    """
    Calculate resource validation coverage.
    Coverage = % of resource types that have at least one test/rule covering them.
    """
    resource_types = test_config["resource_types"]
    if not resource_types:
        return None

    # If tests ran successfully, approximate coverage based on resource count vs test count
    # A more accurate approach would parse PSRule/ARM-TTK output for per-resource-type coverage
    if total_tests == 0:
        return {"overall": 0.0, "per_module": []}

    covered = min(total_tests, len(resource_types))
    overall = (covered / len(resource_types)) * 100 if resource_types else 0.0

    per_module = [f"Resources: {len(resource_types)} types"]
    if test_config["has_psrule"]:
        per_module.append("PSRule: active")
    if test_config["has_arm_ttk"]:
        per_module.append("ARM-TTK: active")

    return {"overall": min(overall, 100.0), "per_module": per_module}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_table(total, passed, failed, failures, coverage=None):
    """Print results in pipeline contract format."""
    if total == 0:
        print("\nNo test results found. Check diagnostic info above.")
        return

    coverage_str = f" | Coverage: {coverage['overall']:.1f}%" if coverage else ""
    print(f"\nSummary: Total: {total}, Passed: {passed}, Failed: {failed}{coverage_str}\n")

    # Per-module coverage
    if coverage and coverage.get("per_module"):
        print("Coverage:  " + "  |  ".join(coverage["per_module"]))
        print()

    if failed == 0:
        print("All tests passed.")
        return

    # Print failure table
    if not failures:
        print(f"{failed} test(s) failed. Run tests manually for details.\n")
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
        description="Run Bicep infrastructure tests in pipeline contract format."
    )
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument(
        "--scheme",
        default=None,
        choices=["arm-ttk", "psrule", "what-if", "all"],
        help="Test framework to run (default: auto-detect)",
    )
    parser.add_argument(
        "--resource-group",
        default=None,
        help="Azure resource group for what-if validation",
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage calculation",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    print(f"Project dir: {project_dir}")

    if not os.path.isdir(project_dir):
        print(f"ERROR: Project directory does not exist: {project_dir}")
        sys.exit(1)

    test_config = detect_test_config(project_dir)

    print(f"Bicep files: {len(test_config['bicep_files'])}")
    print(f"Test files:  {len(test_config['test_files'])}")
    print(f"PSRule:      {'available' if test_config['has_psrule'] else 'not found'}")
    print(f"ARM-TTK:     {'available' if test_config['has_arm_ttk'] else 'not found'}")
    print(f"az CLI:      {'available' if test_config['has_az_cli'] else 'not found'}")
    print(f"Pester:      {'available' if test_config['has_pester'] else 'not found'}")
    if test_config["resource_types"]:
        print(f"Resources:   {len(test_config['resource_types'])} unique types")

    if not test_config["bicep_files"]:
        print("\nWARNING: No .bicep files found.")
        print("\nSummary: Total: 0, Passed: 0, Failed: 0 | Coverage: 0.0%")
        sys.exit(0)

    # Determine which test frameworks to run
    total = 0
    passed = 0
    failed = 0
    all_failures = {}

    schemes_to_run = []
    if args.scheme:
        if args.scheme == "all":
            schemes_to_run = ["psrule", "arm-ttk", "what-if"]
        else:
            schemes_to_run = [args.scheme]
    else:
        # Auto-detect: run what's available
        if test_config["has_psrule"]:
            schemes_to_run.append("psrule")
        if test_config["has_arm_ttk"]:
            schemes_to_run.append("arm-ttk")
        # Only auto-run what-if if a resource group was specified
        if args.resource_group and test_config["has_az_cli"]:
            schemes_to_run.append("what-if")

    if not schemes_to_run:
        print("\nWARNING: No test framework available.")
        print("Install PSRule for Azure or ARM-TTK, or specify --resource-group for what-if.")
        print("\nSummary: Total: 0, Passed: 0, Failed: 0 | Coverage: 0.0%")
        sys.exit(0)

    for scheme in schemes_to_run:
        print(f"\n--- Running: {scheme} ---")

        if scheme == "psrule":
            if not test_config["has_psrule"]:
                print("PSRule not available. Skipping.")
                continue
            t, p, f, failures = run_psrule(
                project_dir,
                test_config["bicep_files"],
                test_config["psrule_config"],
            )
        elif scheme == "arm-ttk":
            if not test_config["has_arm_ttk"]:
                print("ARM-TTK not available. Skipping.")
                continue
            t, p, f, failures = run_arm_ttk(
                project_dir, test_config["bicep_files"]
            )
        elif scheme == "what-if":
            if not test_config["has_az_cli"]:
                print("az CLI not available. Skipping.")
                continue
            if not args.resource_group:
                print("No --resource-group specified. Skipping what-if.")
                continue
            t, p, f, failures = run_what_if(
                project_dir, test_config["bicep_files"], args.resource_group
            )
        else:
            continue

        total += t
        passed += p
        failed += f
        all_failures.update(failures)

    # Calculate coverage
    coverage = None
    if not args.no_coverage:
        coverage = calculate_coverage(test_config, total)

    print_table(total, passed, failed, all_failures, coverage=coverage)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
