"""Property-based oracle for the LRU cache benchmark.

Run from the project root:
    python3 fixtures/property_tests.py [--project=PATH] [--runs=N]

Exit codes:
    0 — all properties hold
    1 — at least one property failed
    2 — class not discoverable

The oracle compares the candidate cache against a reference implementation
backed by ``collections.OrderedDict``. The candidate is asked (in the frozen
feature request) not to use OrderedDict, so the reference is independent.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

# Allow `python3 fixtures/property_tests.py` to find _discover when cwd != fixtures/
sys.path.insert(0, str(Path(__file__).parent))
from _discover import discover  # noqa: E402


# ---------- Reference implementation (independent of the candidate) ----------

class ReferenceLRU:
    """Reference LRU built on OrderedDict. Used only by the oracle."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        self.capacity = capacity
        self._data: "OrderedDict[Any, Any]" = OrderedDict()

    def get(self, key: Any) -> Any:
        if key not in self._data:
            raise KeyError(key)
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: Any, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
            return
        if len(self._data) >= self.capacity:
            self._data.popitem(last=False)  # remove least-recent (front)
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: Any) -> bool:
        return key in self._data


# ---------- Probes (return structured results so we can compare with ==) ----------

def _probe_get(cache: Any, key: Any) -> tuple[str, Any]:
    """Try cache.get(key); return ("ok", value) or ("err", exc_class_name)."""
    try:
        v = cache.get(key)
    except KeyError:
        return ("err", "KeyError")
    except Exception as e:
        return ("err", type(e).__name__)
    return ("ok", v)


def _probe_contains(cache: Any, key: Any) -> bool:
    try:
        return key in cache
    except Exception:
        return False


def _probe_len(cache: Any) -> int | None:
    try:
        return len(cache)
    except Exception:
        return None


# ---------- Op generation ----------

def _gen_ops(rng: random.Random, n_ops: int, key_pool: list[int]) -> list[tuple]:
    """Generate a randomized sequence of put/get ops over a small key pool."""
    ops: list[tuple] = []
    for _ in range(n_ops):
        if rng.random() < 0.6:
            k = rng.choice(key_pool)
            v = rng.randint(0, 1000)
            ops.append(("put", k, v))
        else:
            k = rng.choice(key_pool)
            ops.append(("get", k))
    return ops


# ---------- Suites ----------

def _check_op_sequence_match(LRUClass, n_sequences: int, seed: int) -> tuple[int, list[str]]:
    """For each random sequence of ops, candidate state must match the reference."""
    rng = random.Random(seed)
    fails: list[str] = []
    passed = 0
    for seq_id in range(n_sequences):
        capacity = rng.randint(1, 8)
        n_ops = rng.randint(8, 40)
        ops = _gen_ops(rng, n_ops=n_ops, key_pool=list(range(1, 12)))
        try:
            candidate = LRUClass(capacity)
        except Exception as e:
            fails.append(f"seq {seq_id}: LRUClass({capacity}) raised {type(e).__name__}: {e}")
            continue
        ref = ReferenceLRU(capacity)
        seen: set = set()
        ok = True
        for op_idx, op in enumerate(ops):
            kind = op[0]
            if kind == "put":
                _, k, v = op
                seen.add(k)
                try:
                    candidate.put(k, v)
                except Exception as e:
                    fails.append(
                        f"seq {seq_id} op {op_idx} put({k},{v}): "
                        f"candidate raised {type(e).__name__}: {e}"
                    )
                    ok = False
                    break
                ref.put(k, v)
            else:  # "get"
                _, k = op
                seen.add(k)
                cand_r = _probe_get(candidate, k)
                ref_r = _probe_get(ref, k)
                if cand_r != ref_r:
                    fails.append(
                        f"seq {seq_id} op {op_idx} get({k}): "
                        f"candidate={cand_r}, reference={ref_r}"
                    )
                    ok = False
                    break

            cand_len = _probe_len(candidate)
            ref_len = len(ref)
            if cand_len != ref_len:
                fails.append(
                    f"seq {seq_id} op {op_idx} after {op}: "
                    f"len differs (candidate={cand_len}, reference={ref_len})"
                )
                ok = False
                break
            membership_diff = [
                k for k in seen
                if _probe_contains(candidate, k) != (k in ref)
            ]
            if membership_diff:
                fails.append(
                    f"seq {seq_id} op {op_idx} after {op}: "
                    f"membership diverges on keys {sorted(membership_diff)[:5]}"
                )
                ok = False
                break
        if ok:
            passed += 1
    return passed, fails


def _check_capacity_invariant(LRUClass, n_sequences: int, seed: int) -> tuple[int, list[str]]:
    """``len(cache) <= capacity`` after every op."""
    rng = random.Random(seed + 1)
    fails: list[str] = []
    passed = 0
    for seq_id in range(n_sequences):
        capacity = rng.randint(1, 6)
        try:
            cache = LRUClass(capacity)
        except Exception as e:
            fails.append(f"seq {seq_id}: LRUClass({capacity}) raised {type(e).__name__}: {e}")
            continue
        ops = _gen_ops(rng, n_ops=rng.randint(10, 30), key_pool=list(range(1, 8)))
        ok = True
        for op_idx, op in enumerate(ops):
            kind = op[0]
            try:
                if kind == "put":
                    cache.put(op[1], op[2])
                else:
                    try:
                        cache.get(op[1])
                    except KeyError:
                        pass  # missing-key is fine; we're checking capacity
            except Exception as e:
                fails.append(
                    f"seq {seq_id} op {op_idx} {op}: raised {type(e).__name__}: {e}"
                )
                ok = False
                break
            n = _probe_len(cache)
            if n is None or n > capacity:
                fails.append(
                    f"seq {seq_id} op {op_idx} after {op}: len={n} > capacity={capacity}"
                )
                ok = False
                break
        if ok:
            passed += 1
    return passed, fails


def _check_round_trip_put_get(LRUClass, n_runs: int, seed: int) -> tuple[int, list[str]]:
    """``put(k, v)`` followed by ``get(k)`` returns ``v``."""
    rng = random.Random(seed + 2)
    fails: list[str] = []
    passed = 0
    for i in range(n_runs):
        capacity = rng.randint(1, 8)
        try:
            cache = LRUClass(capacity)
        except Exception as e:
            fails.append(f"run {i}: LRUClass({capacity}) raised {type(e).__name__}: {e}")
            continue
        k = rng.randint(0, 1000)
        v = rng.randint(0, 1_000_000)
        try:
            cache.put(k, v)
            got = cache.get(k)
        except Exception as e:
            fails.append(f"run {i}: put/get round-trip raised {type(e).__name__}: {e}")
            continue
        if got != v:
            fails.append(f"run {i}: put({k},{v}) then get({k}) = {got!r}, expected {v!r}")
        else:
            passed += 1
    return passed, fails


def _check_eviction_order(LRUClass) -> tuple[int, list[str]]:
    """Hand-crafted scenarios targeting the bugs the issue calls out."""
    fails: list[str] = []

    def s1() -> str | None:
        # cap=2, put A, B, C → A evicted (basic LRU)
        c = LRUClass(2)
        c.put("A", 1)
        c.put("B", 2)
        c.put("C", 3)
        if "A" in c or "B" not in c or "C" not in c:
            return (
                f"cap=2 put A,B,C: expected A evicted; "
                f"got 'A' in c={'A' in c}, 'B' in c={'B' in c}, 'C' in c={'C' in c}"
            )
        return None

    def s2() -> str | None:
        # cap=2, put A, B, get A (touches A), put C → B evicted
        c = LRUClass(2)
        c.put("A", 1)
        c.put("B", 2)
        c.get("A")
        c.put("C", 3)
        if "B" in c or "A" not in c or "C" not in c:
            return (
                f"cap=2 put A,B,get A,put C: expected B evicted; "
                f"got 'A' in c={'A' in c}, 'B' in c={'B' in c}, 'C' in c={'C' in c}"
            )
        return None

    def s3() -> str | None:
        # cap=2, put A, B, re-put A (refresh+update), put C → B evicted; A's value updated
        c = LRUClass(2)
        c.put("A", 1)
        c.put("B", 2)
        c.put("A", 99)
        c.put("C", 3)
        if "B" in c or "A" not in c or "C" not in c:
            return (
                f"cap=2 put A,B,re-put A,put C: expected B evicted; "
                f"got 'A' in c={'A' in c}, 'B' in c={'B' in c}, 'C' in c={'C' in c}"
            )
        if c.get("A") != 99:
            return f"re-put A=99: expected get A == 99, got {c.get('A')!r}"
        return None

    def s4() -> str | None:
        # cap=1, put A, put B → only B remains.
        c = LRUClass(1)
        c.put("A", 1)
        c.put("B", 2)
        if "A" in c or "B" not in c or len(c) != 1:
            return (
                f"cap=1 put A,B: expected only B; "
                f"got 'A' in c={'A' in c}, 'B' in c={'B' in c}, len={len(c)}"
            )
        return None

    scenarios = [
        ("evict_lru_basic", s1),
        ("get_refreshes_recency", s2),
        ("reput_refreshes_recency", s3),
        ("capacity_one", s4),
    ]
    passed = 0
    for name, fn in scenarios:
        try:
            err = fn()
        except Exception as e:
            err = f"raised {type(e).__name__}: {e}"
        if err is None:
            passed += 1
        else:
            fails.append(f"{name}: {err}")
    return passed, fails


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.getcwd(), help="Project root containing src/")
    parser.add_argument("--runs", type=int, default=1000,
                        help="Number of randomized runs for the parity suite (others scale down)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", default=None, help="Write structured results to this path")
    parser.add_argument("--max-fails-shown", type=int, default=5)
    args = parser.parse_args()

    try:
        LRUClass = discover(Path(args.project))
    except ImportError as e:
        print(f"DISCOVERY FAILED: {e}")
        if args.json:
            Path(args.json).write_text(json.dumps({"error": "discovery_failed", "detail": str(e)}))
        return 2

    n_seq_full = args.runs
    n_seq_inv = max(1, args.runs // 4)
    n_seq_rt = max(1, args.runs // 2)

    suites = [
        ("op_sequence_match",  lambda: _check_op_sequence_match(LRUClass, n_seq_full, args.seed),  n_seq_full),
        ("capacity_invariant", lambda: _check_capacity_invariant(LRUClass, n_seq_inv, args.seed),  n_seq_inv),
        ("round_trip_put_get", lambda: _check_round_trip_put_get(LRUClass, n_seq_rt, args.seed),   n_seq_rt),
        ("eviction_order",     lambda: _check_eviction_order(LRUClass),                            4),
    ]

    suite_results: dict[str, dict] = {}
    total_pass = 0
    total_run = 0
    any_fail = False

    for name, fn, run_count in suites:
        passed, fails = fn()
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
    print(f"Property suite — class: {LRUClass.__module__}.{LRUClass.__name__}")
    for name, r in suite_results.items():
        status = "OK" if r["failure_count"] == 0 else f"FAIL ({r['failure_count']})"
        print(f"  {name:<22} {r['passed']:>5}/{r['total']:<5}  [{status}]")
        for f in r["failures_sample"]:
            print(f"      - {f}")
    print(f"Summary: Passed: {total_pass}/{total_run} ({pct:.1f}%)")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "module": f"{LRUClass.__module__}.{LRUClass.__name__}",
            "suites": suite_results,
            "total_passed": total_pass,
            "total_run": total_run,
            "pass_pct": pct,
        }, indent=2))

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
