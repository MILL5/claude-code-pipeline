#!/usr/bin/env python3
"""
Run Swift/Xcode build and output only errors in a minimal table.
Usage: python build.py [--project-dir /path/to/project] [--scheme SchemeName] [--configuration Debug|Release]
"""

import subprocess
import sys
import re
import argparse
import os


def list_schemes(project_dir, xcodeproj=None, xcworkspace=None):
    """List available schemes from the Xcode project/workspace."""
    if xcodeproj:
        cmd = ["xcodebuild", "-list", "-project", xcodeproj]
    elif xcworkspace:
        cmd = ["xcodebuild", "-list", "-workspace", xcworkspace]
    else:
        return []

    try:
        result = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True, timeout=30
        )
        schemes = []
        in_schemes = False
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped == "Schemes:":
                in_schemes = True
                continue
            if in_schemes:
                if not stripped or (stripped and not line.startswith("    ")):
                    break
                schemes.append(stripped)
        return schemes
    except Exception as e:
        print(f"Warning: Could not list schemes ({e})")
        return []


def pick_scheme(schemes, prefer_watch=False):
    """Pick the best scheme from a list."""
    if not schemes:
        return None
    if prefer_watch:
        watch = [s for s in schemes if "Watch" in s]
        return watch[0] if watch else schemes[0]
    else:
        # Prefer non-Watch, non-Widget schemes (the main app)
        main = [s for s in schemes if "Watch" not in s and "Widget" not in s]
        return main[0] if main else schemes[0]


def run_build(project_dir=".", scheme=None, configuration="Debug"):
    entries = os.listdir(project_dir)
    xcworkspace = next((e for e in entries if e.endswith(".xcworkspace")), None)
    xcodeproj = next((e for e in entries if e.endswith(".xcodeproj")), None)
    has_package = "Package.swift" in entries

    # Auto-discover scheme if not provided
    if not scheme and xcodeproj:
        schemes = list_schemes(project_dir, xcodeproj=xcodeproj)
        if schemes:
            scheme = pick_scheme(schemes)
            print(f"Auto-detected scheme: {scheme}")
        else:
            print("Warning: Could not discover schemes; building without -scheme flag")
    elif not scheme and xcworkspace:
        schemes = list_schemes(project_dir, xcworkspace=xcworkspace)
        if schemes:
            scheme = pick_scheme(schemes)
            print(f"Auto-detected scheme: {scheme}")

    # Determine destination based on scheme
    destination = "generic/platform=iOS"
    if scheme and "Watch" in scheme:
        destination = "generic/platform=watchOS"

    if xcodeproj:
        cmd = ["xcodebuild", "build",
               "-project", xcodeproj,
               "-destination", destination,
               "-configuration", configuration]
        if scheme:
            cmd += ["-scheme", scheme]
    elif xcworkspace:
        cmd = ["xcodebuild", "build",
               "-workspace", xcworkspace,
               "-destination", destination,
               "-configuration", configuration]
        if scheme:
            cmd += ["-scheme", scheme]
    elif has_package:
        cmd = ["swift", "build"]
        if configuration.lower() == "release":
            cmd += ["-c", "release"]
    else:
        print("ERROR: No Xcode project, workspace, or Package.swift found in:")
        print(f"  {os.path.abspath(project_dir)}")
        print("Contents:", entries[:10])
        sys.exit(1)

    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True
    )

    return result.stdout + result.stderr, result.returncode


def parse_errors(output):
    errors = []
    warnings = []

    # Pattern: /path/to/File.swift:10:5: error: message
    diag_pattern = re.compile(
        r"([^/\s][^\n]*?\.swift):(\d+):(\d+):\s+(error|warning):\s+(.+)"
    )

    seen = set()
    for m in diag_pattern.finditer(output):
        filepath, line, col, severity, message = m.groups()
        parts = filepath.replace("\\", "/").split("/")
        short_path = "/".join(parts[-2:]) if len(parts) > 2 else filepath
        message = message.strip()[:100]
        key = (short_path, line, message)
        if key in seen:
            continue
        seen.add(key)

        entry = {"file": short_path, "line": line, "col": col, "msg": message}
        if severity == "error":
            errors.append(entry)
        else:
            warnings.append(entry)

    # Also catch linker errors and other non-file errors
    linker_pattern = re.compile(r"^(ld: .+|clang: error: .+|error: .+)", re.MULTILINE)
    for m in linker_pattern.finditer(output):
        msg = m.group(1).strip()[:100]
        if not any(e["msg"] == msg for e in errors):
            errors.append({"file": "-", "line": "-", "col": "-", "msg": msg})

    return errors, warnings


def print_table(errors, warnings, returncode, raw_output=None):
    if returncode == 0 and not errors:
        print(f"BUILD SUCCEEDED  |  {len(warnings)} warning(s)")
        return

    print(f"\nBUILD FAILED  |  {len(errors)} error(s)  |  {len(warnings)} warning(s)\n")

    if not errors:
        print("No parseable errors found. Showing relevant build output:\n")
        if raw_output:
            lines = raw_output.split('\n')
            filtered = []
            for line in lines:
                if any(skip in line for skip in ['{ platform:', 'Compiling', 'Linking', 'Generate', 'Processing']):
                    continue
                if line.strip():
                    filtered.append(line)

            problem_lines = [l for l in filtered if any(kw in l.lower() for kw in ['error', 'failed', 'fatal', 'issue', 'cannot find'])]
            if problem_lines:
                print('\n'.join(problem_lines[:30]))
            else:
                print('\n'.join(filtered[-30:]))
        sys.exit(1)

    fw = max(len(e["file"]) for e in errors)
    lw = max(len(e["line"]) for e in errors)
    mw = max(len(e["msg"]) for e in errors)

    header = f"{'File':<{fw}}  {'Ln':>{lw}}  {'Error'}"
    print(header)
    print("-" * min(len(header) + mw, 120))

    for e in errors:
        print(f"{e['file']:<{fw}}  {e['line']:>{lw}}  {e['msg']}")

    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--scheme", default=None, help="Xcode scheme name")
    parser.add_argument("--configuration", default="Debug", help="Build configuration (Debug/Release)")
    args = parser.parse_args()

    print(f"Building in: {os.path.abspath(args.project_dir)}")
    output, returncode = run_build(args.project_dir, args.scheme, args.configuration)
    errors, warnings = parse_errors(output)
    print_table(errors, warnings, returncode, output)

    if returncode != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
