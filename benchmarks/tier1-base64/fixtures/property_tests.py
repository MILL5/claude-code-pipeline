"""Property-based oracle for the base64 round-trip benchmark.

Run from the project root:
    python3 fixtures/property_tests.py [--project=PATH] [--runs=N]

Exit codes:
    0 — all properties hold
    1 — at least one property failed
    2 — module not discoverable
"""

from __future__ import annotations

import argparse
import base64 as _stdlib_base64
import json
import os
import random
import string
import sys
from pathlib import Path

# Allow `python3 fixtures/property_tests.py` to find _discover when cwd != fixtures/
sys.path.insert(0, str(Path(__file__).parent))
from _discover import discover  # noqa: E402

ALPHABET = set(string.ascii_letters + string.digits + "+/=")


def _gen_inputs(n_runs: int, seed: int) -> list[bytes]:
    rng = random.Random(seed)
    inputs: list[bytes] = [b""]
    inputs.extend(bytes([0]) * k for k in range(1, 4))
    inputs.extend(bytes([0xFF]) * k for k in range(1, 4))
    inputs.extend(bytes(range(256)) for _ in range(2))
    while len(inputs) < n_runs:
        length = rng.randint(0, 256)
        inputs.append(bytes(rng.randint(0, 255) for _ in range(length)))
    return inputs[:n_runs]


def _check_round_trip(mod, inputs: list[bytes]) -> tuple[int, list[str]]:
    fails: list[str] = []
    passed = 0
    for x in inputs:
        try:
            got = mod.decode(mod.encode(x))
        except Exception as e:
            fails.append(f"round_trip raised on len={len(x)}: {type(e).__name__}: {e}")
            continue
        if got != x:
            fails.append(f"round_trip mismatch on len={len(x)}: got {got!r}, expected {x!r}")
        else:
            passed += 1
    return passed, fails


def _check_alphabet(mod, inputs: list[bytes]) -> tuple[int, list[str]]:
    fails: list[str] = []
    passed = 0
    for x in inputs:
        try:
            s = mod.encode(x)
        except Exception as e:
            fails.append(f"encode raised on len={len(x)}: {e}")
            continue
        bad = [c for c in s if c not in ALPHABET]
        if bad:
            fails.append(f"alphabet violation on len={len(x)}: bad chars {bad[:5]}")
        else:
            passed += 1
    return passed, fails


def _check_padding(mod, inputs: list[bytes]) -> tuple[int, list[str]]:
    fails: list[str] = []
    passed = 0
    for x in inputs:
        try:
            s = mod.encode(x)
        except Exception as e:
            fails.append(f"encode raised on len={len(x)}: {e}")
            continue
        if len(s) % 4 != 0:
            fails.append(f"length not multiple of 4 on len={len(x)}: encoded len={len(s)}")
            continue
        # Padding `=` may only appear at the end
        if "=" in s:
            first_eq = s.index("=")
            if not all(c == "=" for c in s[first_eq:]):
                fails.append(f"padding not at end on len={len(x)}: {s!r}")
                continue
            if s.count("=") > 2:
                fails.append(f"too much padding on len={len(x)}: {s!r}")
                continue
        passed += 1
    return passed, fails


def _check_empty(mod) -> tuple[int, list[str]]:
    fails: list[str] = []
    try:
        if mod.encode(b"") != "":
            fails.append(f"encode(b'') != '' (got {mod.encode(b'')!r})")
        if mod.decode("") != b"":
            fails.append(f"decode('') != b'' (got {mod.decode('')!r})")
    except Exception as e:
        fails.append(f"empty round-trip raised: {type(e).__name__}: {e}")
    return (1 if not fails else 0), fails


def _check_reference(mod, inputs: list[bytes]) -> tuple[int, list[str]]:
    fails: list[str] = []
    passed = 0
    for x in inputs:
        try:
            got = mod.encode(x)
        except Exception as e:
            fails.append(f"encode raised on len={len(x)}: {e}")
            continue
        expected = _stdlib_base64.b64encode(x).decode("ascii")
        if got != expected:
            fails.append(f"reference mismatch on len={len(x)}: got {got!r}, expected {expected!r}")
        else:
            passed += 1
    return passed, fails


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.getcwd(), help="Project root containing src/")
    parser.add_argument("--runs", type=int, default=1000, help="Number of fuzzed inputs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", default=None, help="Write structured results to this path")
    parser.add_argument("--max-fails-shown", type=int, default=5)
    args = parser.parse_args()

    try:
        mod = discover(Path(args.project))
    except ImportError as e:
        print(f"DISCOVERY FAILED: {e}")
        if args.json:
            Path(args.json).write_text(json.dumps({"error": "discovery_failed", "detail": str(e)}))
        return 2

    inputs = _gen_inputs(args.runs, args.seed)

    suites = [
        ("round_trip",         lambda: _check_round_trip(mod, inputs)),
        ("alphabet",           lambda: _check_alphabet(mod, inputs)),
        ("padding",            lambda: _check_padding(mod, inputs)),
        ("empty_round_trip",   lambda: _check_empty(mod)),
        ("reference_match",    lambda: _check_reference(mod, inputs)),
    ]

    suite_results: dict[str, dict] = {}
    total_pass = 0
    total_run = 0
    any_fail = False

    for name, fn in suites:
        passed, fails = fn()
        run_count = len(inputs) if name != "empty_round_trip" else 1
        suite_results[name] = {
            "passed": passed,
            "total": run_count,
            "failures_sample": fails[: args.max_fails_shown],
            "failure_count": len(fails),
        }
        total_pass += passed
        total_run += run_count
        if fails:
            any_fail = True

    pct = 100.0 * total_pass / total_run if total_run else 0.0
    print(f"Property suite — module: {mod.__name__}")
    for name, r in suite_results.items():
        status = "OK" if r["failure_count"] == 0 else f"FAIL ({r['failure_count']})"
        print(f"  {name:<22} {r['passed']:>5}/{r['total']:<5}  [{status}]")
        for f in r["failures_sample"]:
            print(f"      - {f}")
    print(f"Summary: Passed: {total_pass}/{total_run} ({pct:.1f}%)")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "module": mod.__name__,
            "suites": suite_results,
            "total_passed": total_pass,
            "total_run": total_run,
            "pass_pct": pct,
        }, indent=2))

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
