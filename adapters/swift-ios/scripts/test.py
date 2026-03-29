#!/usr/bin/env python3
"""
Run Swift unit tests (Xcode or SPM) and output a minimal results table.

Usage examples:
  # Auto-detect everything
  python test.py --project-dir .

  # For watchOS scheme
  python test.py --project-dir . --scheme "MyApp Watch App" --destination "platform=watchOS Simulator,name=Apple Watch SE (44mm)"

  # For iOS/iPhone scheme
  python test.py --project-dir . --scheme "MyApp" --destination "platform=iOS Simulator,name=iPhone 16"

  # For Swift Package (no scheme/destination needed)
  python test.py --project-dir .
"""
import subprocess
import sys
import re
import argparse
import os
import json
import shutil


# ---------------------------------------------------------------------------
# Scheme discovery
# ---------------------------------------------------------------------------

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
        main = [s for s in schemes if "Watch" not in s and "Widget" not in s]
        return main[0] if main else schemes[0]


# ---------------------------------------------------------------------------
# Simulator resolution
# ---------------------------------------------------------------------------

def _device_name_matches(candidate_name, requested_name):
    """
    Return True if candidate_name is an exact match for requested_name,
    or starts with requested_name followed by a space or '(' (generation suffix).
    This avoids 'iPhone 16' matching 'iPhone 16 Pro'.
    """
    if candidate_name == requested_name:
        return True
    if candidate_name.startswith(requested_name):
        next_char = candidate_name[len(requested_name)]
        return next_char in (' ', '(')
    return False


def _pick_newest_simulator(platform, device_prefix):
    """
    Pick the newest available simulator matching device_prefix on the highest OS.
    Returns a destination string like 'platform=iOS Simulator,id=XXXX' or None.
    """
    if "iOS" in platform:
        runtime_prefix = "com.apple.CoreSimulator.SimRuntime.iOS"
    elif "watchOS" in platform:
        runtime_prefix = "com.apple.CoreSimulator.SimRuntime.watchOS"
    else:
        return None

    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "--json"],
            capture_output=True, text=True, check=False
        )
        data = json.loads(result.stdout)
        devices = data.get("devices", {})
        all_devices = []

        for runtime_id, device_list in devices.items():
            if not runtime_id.startswith(runtime_prefix):
                continue
            os_match = re.search(r"-(\d+)-(\d+)(?:-(\d+))?$", runtime_id)
            if not os_match:
                continue
            major = int(os_match.group(1))
            minor = int(os_match.group(2))
            patch = int(os_match.group(3)) if os_match.group(3) else 0
            os_ver = (major, minor, patch)

            for dev in device_list:
                if not dev.get("isAvailable", False):
                    continue
                if device_prefix and device_prefix in dev.get("name", ""):
                    all_devices.append((os_ver, dev["udid"], dev["name"]))

        if not all_devices:
            return None

        # Sort by OS version descending, then by name for consistency
        all_devices.sort(key=lambda x: (x[0], x[2]), reverse=True)
        best = all_devices[0]
        best_os = ".".join(str(x) for x in best[0][:2])
        print(f"Picked newest simulator: '{best[2]}' (OS {best_os})")
        return f"platform={platform},id={best[1]}"

    except Exception:
        return None


def _get_deployment_target(project_dir, scheme, platform_key="iOS"):
    """
    Try to read the deployment target from build settings.
    Returns a (major, minor) tuple or None.
    """
    entries = os.listdir(project_dir)
    xcodeproj = next((e for e in entries if e.endswith(".xcodeproj")), None)
    if not xcodeproj or not scheme:
        return None
    try:
        cmd = [
            "xcodebuild", "-showBuildSettings",
            "-project", xcodeproj,
            "-scheme", scheme,
            "-json"
        ]
        r = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        for entry in data:
            settings = entry.get("buildSettings", {})
            target_key = "IPHONEOS_DEPLOYMENT_TARGET" if platform_key == "iOS" else "WATCHOS_DEPLOYMENT_TARGET"
            val = settings.get(target_key, "")
            if val:
                parts = val.split(".")
                return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except Exception:
        pass
    return None


def resolve_simulator_destination(destination, project_dir=".", scheme=None):
    """
    If destination contains 'platform=iOS Simulator' or 'platform=watchOS Simulator'
    with a name but no explicit id or OS, resolve to a concrete device id using
    xcrun simctl so xcodebuild doesn't pick OS:latest (which may not have that device).

    When the requested device name doesn't exist on a runtime that meets the project's
    deployment target, falls back to the newest available device on the highest OS.

    Returns the (possibly updated) destination string.
    """
    if not destination:
        return destination

    # Only attempt resolution when no id or OS is already specified
    if "id=" in destination or "OS=" in destination:
        return destination

    platform_match = re.search(r"platform=([^,]+)", destination)
    name_match = re.search(r"name=([^,]+)", destination)
    if not platform_match or not name_match:
        return destination

    platform = platform_match.group(1).strip()
    device_name = name_match.group(1).strip()

    if "iOS Simulator" in platform:
        runtime_prefix = "com.apple.CoreSimulator.SimRuntime.iOS"
        platform_key = "iOS"
    elif "watchOS Simulator" in platform:
        runtime_prefix = "com.apple.CoreSimulator.SimRuntime.watchOS"
        platform_key = "watchOS"
    else:
        return destination

    # Read project deployment target to filter out incompatible runtimes
    min_os = _get_deployment_target(project_dir, scheme, platform_key)
    if min_os:
        print(f"Deployment target: {platform_key} {min_os[0]}.{min_os[1]}")

    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "--json"],
            capture_output=True, text=True, check=False
        )
        data = json.loads(result.stdout)
        devices = data.get("devices", {})

        # Collect exact and generation-suffix matches, plus all available devices
        candidates = []        # (os_ver_tuple, udid, name)
        partial_candidates = []
        all_platform_devices = []

        for runtime_id, device_list in devices.items():
            if not runtime_id.startswith(runtime_prefix):
                continue
            os_match = re.search(r"-(\d+)-(\d+)(?:-(\d+))?$", runtime_id)
            if not os_match:
                continue
            major = int(os_match.group(1))
            minor = int(os_match.group(2))
            patch = int(os_match.group(3)) if os_match.group(3) else 0
            os_ver = (major, minor, patch)

            # Skip runtimes below deployment target
            if min_os and (major, minor) < min_os:
                continue

            for dev in device_list:
                dev_name = dev.get("name", "")
                if not dev.get("isAvailable", False):
                    continue

                all_platform_devices.append((os_ver, dev["udid"], dev_name))

                if dev_name == device_name:
                    candidates.append((os_ver, dev["udid"], dev_name))
                elif _device_name_matches(dev_name, device_name):
                    partial_candidates.append((os_ver, dev["udid"], dev_name))

        if not candidates and partial_candidates:
            candidates = partial_candidates

        if not all_platform_devices:
            print(f"Warning: No available simulators found for platform '{platform}'. Trying original destination.")
            return destination

        all_platform_devices.sort(key=lambda x: x[0], reverse=True)

        if not candidates:
            # Device model not found on a compatible runtime — pick best available
            if "iOS" in runtime_prefix:
                preferred = [d for d in all_platform_devices if "iPhone" in d[2]]
            else:
                preferred = [d for d in all_platform_devices if "Apple Watch" in d[2]]
            fallback_pool = preferred if preferred else all_platform_devices
            best = fallback_pool[0]
            best_os = ".".join(str(x) for x in best[0][:2])
            print(f"No simulator matching '{device_name}' on {platform_key} >= {min_os[0]}.{min_os[1] if min_os else 0}. Using '{best[2]}' (OS {best_os})")
            return f"platform={platform},id={best[1]}"

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_udid = candidates[0][1]
        best_os = ".".join(str(x) for x in candidates[0][0][:2])
        best_name = candidates[0][2]

        if best_name != device_name:
            print(f"Resolved '{device_name}' -> '{best_name}' id={best_udid} (OS {best_os})")
        else:
            print(f"Resolved '{device_name}' -> id={best_udid} (OS {best_os})")
        return f"platform={platform},id={best_udid}"

    except Exception as e:
        print(f"Warning: Could not resolve simulator ({e}). Trying original destination.")
        return destination


def extract_udid(destination):
    """Extract device UDID from a resolved destination string."""
    if not destination:
        return None
    m = re.search(r"id=([A-F0-9\-]{36})", destination, re.IGNORECASE)
    return m.group(1) if m else None


def boot_simulator(destination):
    """Boot the simulator so it's ready before xcodebuild launches it."""
    udid = extract_udid(destination)
    if not udid:
        return None

    # Check current state
    result = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "--json"],
        capture_output=True, text=True, check=False
    )
    try:
        data = json.loads(result.stdout)
        for device_list in data.get("devices", {}).values():
            for dev in device_list:
                if dev.get("udid") == udid:
                    state = dev.get("state", "")
                    if state == "Booted":
                        print(f"Simulator already booted (id={udid[:8]}...)")
                        return None  # Already up — don't shut it down later
                    break
    except Exception:
        pass

    print(f"Booting simulator (id={udid[:8]}...)...", flush=True)
    try:
        subprocess.run(
            ["xcrun", "simctl", "boot", udid],
            capture_output=True,
            timeout=60
        )
    except subprocess.TimeoutExpired:
        print("Warning: Simulator boot timed out — xcodebuild will handle it.")
        return None

    return udid  # Caller should shut this down after tests


def shutdown_simulator(udid):
    """Shutdown a simulator by UDID."""
    if not udid:
        return
    print(f"Shutting down simulator (id={udid[:8]}...)")
    subprocess.run(["xcrun", "simctl", "shutdown", udid], capture_output=True)


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def run_swift_tests(project_dir=".", scheme=None, destination=None, coverage=True):
    entries = os.listdir(project_dir)
    xcodeproj = next((e for e in entries if e.endswith(".xcodeproj")), None)
    xcworkspace = next((e for e in entries if e.endswith(".xcworkspace")), None)
    has_package = "Package.swift" in entries

    if has_package and not xcodeproj and not xcworkspace:
        cmd = ["swift", "test"]
        result = subprocess.run(
            cmd, cwd=project_dir, capture_output=True, text=True, check=False
        )
        return result.stdout + result.stderr, result.returncode, None

    # Xcode project/workspace — auto-discover scheme if needed
    if not scheme:
        schemes = list_schemes(project_dir, xcodeproj=xcodeproj, xcworkspace=xcworkspace)
        if schemes:
            scheme = pick_scheme(schemes)
            print(f"Auto-detected scheme: {scheme}")
        else:
            print("ERROR: Could not discover any schemes. Pass --scheme explicitly.")
            sys.exit(1)

    # Auto-detect destination: pick the newest available simulator on the highest OS
    if not destination:
        if "Watch" in scheme:
            destination = _pick_newest_simulator("watchOS Simulator", "Apple Watch")
            if not destination:
                destination = "platform=watchOS Simulator,name=Apple Watch Series 10 (42mm)"
        else:
            destination = _pick_newest_simulator("iOS Simulator", "iPhone")
            if not destination:
                destination = "platform=iOS Simulator,name=iPhone 16"
        print(f"Auto-detected destination: {destination}")
        # Resolve to concrete device id if still name-based
        destination = resolve_simulator_destination(destination, project_dir, scheme)

    xcresult_path = "/tmp/pipeline-test-results.xcresult"
    if os.path.exists(xcresult_path):
        shutil.rmtree(xcresult_path)

    if xcworkspace:
        cmd = [
            "xcodebuild", "test",
            "-workspace", xcworkspace,
            "-scheme", scheme,
            "-destination", destination,
            "-resultBundlePath", xcresult_path,
        ]
    elif xcodeproj:
        cmd = [
            "xcodebuild", "test",
            "-project", xcodeproj,
            "-scheme", scheme,
            "-destination", destination,
            "-resultBundlePath", xcresult_path,
        ]
    else:
        print("ERROR: No .xcodeproj, .xcworkspace, or Package.swift found.")
        sys.exit(1)

    if coverage:
        cmd += ["-enableCodeCoverage", "YES"]

    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True, check=False
    )
    return result.stdout + result.stderr, result.returncode, xcresult_path


# ---------------------------------------------------------------------------
# xcresult parsing
# ---------------------------------------------------------------------------

def _xcresult_get(xcresult_path, ref_id=None):
    """Fetch an object from the xcresult bundle. Tries modern format, then legacy."""
    for extra in ([], ["--legacy"]):
        cmd = ["xcrun", "xcresulttool", "get", "object",
               "--format", "json", "--path", xcresult_path] + extra
        if ref_id:
            cmd += ["--id", ref_id]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return json.loads(r.stdout)
        except Exception:
            continue
    return {}


def extract_failures_from_xcresult(xcresult_path):
    """Extract per-test failure messages from xcresult bundle."""
    failures = {}
    if not xcresult_path or not os.path.exists(xcresult_path):
        return failures

    try:
        top = _xcresult_get(xcresult_path)
        tests_ref_id = None
        for action in top.get("actions", {}).get("_values", []):
            tests_ref_id = action.get("actionResult", {}).get("testsRef", {}).get("id", {}).get("_value")
            if tests_ref_id:
                break
        if not tests_ref_id:
            return failures

        tests_data = _xcresult_get(xcresult_path, tests_ref_id)
        failing = []

        def walk(node):
            if isinstance(node, dict):
                if node.get("_type", {}).get("_name") == "ActionTestMetadata":
                    if node.get("testStatus", {}).get("_value") == "Failure":
                        identifier = node.get("identifier", {}).get("_value", "")
                        parts = identifier.split("/")
                        if len(parts) == 2:
                            key = f"{parts[0]}.{parts[1].rstrip('()')}"
                            ref = node.get("summaryRef", {}).get("id", {}).get("_value")
                            if ref:
                                failing.append((key, ref))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for i in node:
                    walk(i)

        walk(tests_data)

        for key, ref_id in failing:
            summary = _xcresult_get(xcresult_path, ref_id)
            msgs = []
            for f in summary.get("failureSummaries", {}).get("_values", []):
                msg = f.get("message", {}).get("_value", "").strip()
                if msg:
                    msgs.append(msg)
            if msgs:
                failures[key] = " | ".join(msgs)[:160]

    except Exception as e:
        print(f"Warning: Could not parse xcresult ({e})")

    return failures


def _file_matches_any_pattern(file_path, patterns):
    """
    Check if a file path matches any of the exclusion patterns.
    Supports simple glob-like patterns:
      - '*View.swift'    matches files ending in View.swift
      - '*/Views/*'      matches files with /Views/ in path
      - '*Widget*'       matches files with Widget in name
    """
    import fnmatch
    basename = os.path.basename(file_path)
    for pattern in patterns:
        # Match against full path and basename
        if fnmatch.fnmatch(file_path, pattern):
            return True
        if fnmatch.fnmatch(basename, pattern):
            return True
        # Also check if pattern appears as a path component
        if '/' in pattern and fnmatch.fnmatch(file_path, f"*{pattern}*"):
            return True
    return False


def extract_coverage_from_xcresult(xcresult_path, exclude_patterns=None):
    """
    Extract code coverage summary from xcresult bundle using xcrun xccov.
    Returns a dict with 'overall' (float %) and 'per_target' (list of strings),
    or None if coverage data is unavailable.

    If exclude_patterns is provided, files matching any pattern are excluded from
    the coverage calculation (but still reported in a separate 'excluded_summary').
    """
    if not xcresult_path or not os.path.exists(xcresult_path):
        return None
    try:
        r = subprocess.run(
            ["xcrun", "xccov", "view", "--report", "--json", xcresult_path],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        data = json.loads(r.stdout)
        targets = data.get("targets", [])
        if not targets:
            return None

        # Exclude test bundles and system frameworks — only count app/extension targets
        app_targets = [
            t for t in targets
            if not t.get("name", "").endswith("Tests.xctest")
            and not t.get("name", "").endswith("UITests.xctest")
            and not t.get("name", "").startswith("/Applications/")
        ]
        if not app_targets:
            app_targets = targets

        total_executable = 0
        total_covered = 0
        excluded_executable = 0
        excluded_covered = 0
        per_target = []

        for t in sorted(app_targets, key=lambda x: x.get("executableLines", 0), reverse=True):
            target_exe = 0
            target_cov = 0
            target_excluded_exe = 0
            target_excluded_cov = 0

            files = t.get("files", [])
            if files and exclude_patterns:
                for f in files:
                    fpath = f.get("path", "")
                    fexe = f.get("executableLines", 0)
                    fcov = f.get("coveredLines", 0)
                    if _file_matches_any_pattern(fpath, exclude_patterns):
                        target_excluded_exe += fexe
                        target_excluded_cov += fcov
                    else:
                        target_exe += fexe
                        target_cov += fcov
            elif files:
                # No exclusions — use file-level totals for consistency
                for f in files:
                    target_exe += f.get("executableLines", 0)
                    target_cov += f.get("coveredLines", 0)
            else:
                # No file-level data — fall back to target-level totals
                target_exe = t.get("executableLines", 0)
                target_cov = t.get("coveredLines", 0)

            total_executable += target_exe
            total_covered += target_cov
            excluded_executable += target_excluded_exe
            excluded_covered += target_excluded_cov

            if target_exe == 0:
                continue
            pct = target_cov / target_exe * 100
            name = t.get("name", "?").replace(".app", "").replace(".appex", "")
            per_target.append(f"{name}: {pct:.1f}%")

        if total_executable == 0:
            return None

        overall_pct = total_covered / total_executable * 100

        result = {"overall": overall_pct, "per_target": per_target}

        if exclude_patterns and excluded_executable > 0:
            result["excluded_lines"] = excluded_executable
            result["excluded_pct"] = excluded_covered / excluded_executable * 100 if excluded_executable else 0

        return result

    except Exception as e:
        print(f"Warning: Could not extract coverage ({e})")
        return None


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def parse_results(output):
    tests = []

    # Modern Xcode format (Xcode 16+)
    modern_pattern = re.compile(
        r"Test case '(\w+)\.(\w+)\(\)' (passed|failed)(?:\s+on\s+'[^']*')?\s+\(([\d.]+) seconds\)"
    )
    for m in modern_pattern.finditer(output):
        cls, method, status, duration = m.groups()
        tests.append({
            "class": cls,
            "test": method,
            "status": "pass" if status == "passed" else "fail",
            "duration": f"{float(duration or 0):.3f}s"
        })

    # Legacy Xcode format (Xcode 15 and earlier)
    if not tests:
        legacy_pattern = re.compile(
            r"Test Case '.*?\[(\S+)\s+(\S+)\]' (passed|failed)(?: \(([\d.]+) seconds\))?"
        )
        for m in legacy_pattern.finditer(output):
            cls, method, status, duration = m.groups()
            tests.append({
                "class": cls,
                "test": method,
                "status": "pass" if status == "passed" else "fail",
                "duration": f"{float(duration or 0):.3f}s" if duration else "-"
            })

    # SPM fallback
    if not tests:
        for m in re.compile(r"Test (\w+)\(\) passed").finditer(output):
            tests.append({"class": "", "test": m.group(1), "status": "pass", "duration": "-"})
        for m in re.compile(r"Test (\w+)\(\) failed").finditer(output):
            tests.append({"class": "", "test": m.group(1), "status": "fail", "duration": "-"})

    # Extract inline failure reasons as fallback when xcresult isn't available
    failures = {}
    modern_fail_pattern = re.compile(
        r"Test case '(\w+)\.(\w+)\(\)' failed.*?\n(.*?)(?=Test case|$)", re.DOTALL
    )
    for m in modern_fail_pattern.finditer(output):
        cls, method, detail = m.groups()
        assertion = re.search(r"error: (.+?)(?:\n|$)", detail)
        if assertion:
            failures[f"{cls}.{method}"] = assertion.group(1).strip()[:120]

    if not failures:
        legacy_fail_pattern = re.compile(
            r"Test Case '.*?\[(\S+)\s+(\S+)\]' failed.*?\n(.*?)(?=Test Case|$)", re.DOTALL
        )
        for m in legacy_fail_pattern.finditer(output):
            cls, method, detail = m.groups()
            assertion = re.search(r"error: (.+?)(?:\n|$)", detail)
            if assertion:
                failures[f"{cls}.{method}"] = assertion.group(1).strip()[:120]

    return tests, failures


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_table(tests, failures, coverage=None):
    if not tests:
        print("No test results parsed. Check diagnostic info above.")
        return

    passed = sum(1 for t in tests if t["status"] == "pass")
    failed_tests = [t for t in tests if t["status"] == "fail"]
    total = len(tests)

    coverage_str = f" | Coverage: {coverage['overall']:.1f}%" if coverage else ""
    print(f"\nSummary: Total: {total}, Passed: {passed}, Failed: {len(failed_tests)}{coverage_str}\n")

    if coverage and coverage["per_target"]:
        print("Coverage:  " + "  |  ".join(coverage["per_target"]))
        if coverage.get("excluded_lines"):
            print(f"Excluded:  {coverage['excluded_lines']} lines ({coverage['excluded_pct']:.1f}% covered) — filtered by --exclude-from-coverage")
        print()

    if not failed_tests:
        print("All tests passed.")
        return

    has_class = any(t["class"] for t in failed_tests)

    if has_class:
        cw = max(len(t["class"]) for t in failed_tests) + 2
        tw = max(len(t["test"]) for t in failed_tests) + 2
        header = f"{'Class':<{cw}} {'Test':<{tw}} {'Time':>8}"
        print(header)
        print("-" * (cw + tw + 10))
        for t in failed_tests:
            key = f"{t['class']}.{t['test']}"
            print(f"{t['class']:<{cw}} {t['test']:<{tw}} {t['duration']:>8}")
            if key in failures:
                print(f"   L {failures[key]}")
    else:
        tw = max(len(t["test"]) for t in failed_tests) + 2
        print(f"{'Test':<{tw}} {'Time':>8}")
        print("-" * (tw + 10))
        for t in failed_tests:
            print(f"{t['test']:<{tw}} {t['duration']:>8}")
            if t["test"] in failures:
                print(f"   L {failures[t['test']]}")

    print()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run unit tests and show minimal pass/fail table.")
    parser.add_argument("--project-dir", default=".", help="Path to project root")
    parser.add_argument("--scheme", help="Xcode scheme name (auto-detected if omitted)")
    parser.add_argument("--destination", help="xcodebuild destination string (auto-detected if omitted)")
    parser.add_argument("--no-coverage", action="store_true", help="Disable code coverage collection")
    parser.add_argument(
        "--exclude-from-coverage",
        nargs="+",
        metavar="PATTERN",
        help="Glob patterns for files to exclude from coverage calculation (e.g. '*View.swift' '*/Views/*')"
    )
    args = parser.parse_args()
    collect_coverage = not args.no_coverage

    print(f"Project dir: {os.path.abspath(args.project_dir)}")
    if args.scheme:
        print(f"Scheme:      {args.scheme}")
    if args.destination:
        print(f"Destination: {args.destination}")

    raw_destination = args.destination
    if not raw_destination and args.scheme:
        if "Watch" in args.scheme:
            raw_destination = _pick_newest_simulator("watchOS Simulator", "Apple Watch")
            if not raw_destination:
                raw_destination = "platform=watchOS Simulator,name=Apple Watch Series 10 (42mm)"
        else:
            raw_destination = _pick_newest_simulator("iOS Simulator", "iPhone")
            if not raw_destination:
                raw_destination = "platform=iOS Simulator,name=iPhone 16"
        print(f"Auto-detected destination: {raw_destination}")

    resolved_destination = resolve_simulator_destination(raw_destination, args.project_dir, args.scheme) if raw_destination else None

    booted_udid = boot_simulator(resolved_destination) if resolved_destination else None

    try:
        output, returncode, xcresult_path = run_swift_tests(
            args.project_dir,
            args.scheme,
            resolved_destination,
            coverage=collect_coverage
        )
    finally:
        shutdown_simulator(booted_udid)

    tests, inline_failures = parse_results(output)
    xcresult_failures = extract_failures_from_xcresult(xcresult_path)
    # Prefer xcresult details; fall back to inline-parsed reasons
    failures = {**inline_failures, **xcresult_failures}

    # Extract coverage before cleaning up the xcresult bundle
    coverage = extract_coverage_from_xcresult(
        xcresult_path,
        exclude_patterns=args.exclude_from_coverage
    ) if collect_coverage else None

    # Clean up the xcresult bundle
    if xcresult_path and os.path.exists(xcresult_path):
        try:
            shutil.rmtree(xcresult_path)
        except Exception as e:
            print(f"Warning: Could not clean up xcresult bundle ({e})")

    print_table(tests, failures, coverage=coverage)

    # Diagnostic output when no results were parsed
    if not tests:
        print("\n--- Diagnostic Info ---")
        if returncode != 0:
            print(f"xcodebuild returned exit code {returncode}")
        else:
            print("Tests ran but no results were parsed.")
            print("Scheme may not have test targets, or output format is unexpected.")

        lines = output.strip().splitlines()
        filtered = [l for l in lines if "{ platform:" not in l]
        display = filtered if filtered else lines
        print("\nLast 50 lines of output:")
        print("\n".join(display[-50:]))

        if returncode != 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
