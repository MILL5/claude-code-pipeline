"""Unit + functional tests for the pipeline-produced LRU cache.

Run from the project root:
    python3 fixtures/unit_tests.py [--project=PATH]

Exit codes:
    0 — all tests pass
    1 — at least one failed
    2 — class not discoverable
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _discover import discover  # noqa: E402


def _run_test(name: str, fn) -> tuple[bool, str]:
    try:
        fn()
        return True, ""
    except AssertionError as e:
        return False, f"AssertionError: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.getcwd())
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    project = Path(args.project)
    try:
        LRUClass = discover(project)
    except ImportError as e:
        print(f"DISCOVERY FAILED: {e}")
        if args.json:
            Path(args.json).write_text(json.dumps({"error": "discovery_failed", "detail": str(e)}))
        return 2

    def t_class_exists() -> None:
        assert LRUClass is not None

    def t_init_rejects_zero_capacity() -> None:
        try:
            LRUClass(0)
        except ValueError:
            return
        except Exception as e:
            raise AssertionError(
                f"expected ValueError for capacity=0, got {type(e).__name__}: {e}"
            ) from e
        raise AssertionError("expected ValueError for capacity=0, no exception raised")

    def t_init_rejects_negative_capacity() -> None:
        try:
            LRUClass(-1)
        except ValueError:
            return
        except Exception as e:
            raise AssertionError(
                f"expected ValueError for capacity=-1, got {type(e).__name__}: {e}"
            ) from e
        raise AssertionError("expected ValueError for capacity=-1, no exception raised")

    def t_get_missing_raises_key_error() -> None:
        c = LRUClass(2)
        try:
            c.get("nope")
        except KeyError:
            return
        except Exception as e:
            raise AssertionError(
                f"expected KeyError on missing, got {type(e).__name__}: {e}"
            ) from e
        raise AssertionError("expected KeyError on missing key, no exception raised")

    def t_len_initial_zero() -> None:
        c = LRUClass(3)
        assert len(c) == 0, f"len of empty cache should be 0, got {len(c)}"

    def t_len_grows_to_capacity() -> None:
        c = LRUClass(3)
        c.put("a", 1)
        assert len(c) == 1
        c.put("b", 2)
        assert len(c) == 2
        c.put("c", 3)
        assert len(c) == 3
        c.put("d", 4)
        assert len(c) == 3, f"len should stay at capacity=3 after eviction, got {len(c)}"

    def t_capacity_one_eviction() -> None:
        c = LRUClass(1)
        c.put("a", 1)
        c.put("b", 2)
        assert "a" not in c, "expected 'a' to be evicted in capacity=1 cache"
        assert "b" in c, "expected 'b' to remain"
        assert c.get("b") == 2, f"expected get('b')==2, got {c.get('b')!r}"

    def t_update_existing_key_does_not_grow() -> None:
        c = LRUClass(2)
        c.put("a", 1)
        c.put("a", 2)
        assert len(c) == 1, f"re-putting same key should not grow length, got len={len(c)}"
        assert c.get("a") == 2, f"re-put value should be 2, got {c.get('a')!r}"

    def t_get_refreshes_recency() -> None:
        c = LRUClass(2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")           # bump a to MRU
        c.put("c", 3)        # should evict b, not a
        assert "a" in c, "get() should have refreshed a's recency"
        assert "b" not in c, "expected b (not a) to be evicted after get(a)"
        assert "c" in c

    def t_contains_does_not_touch_recency() -> None:
        c = LRUClass(2)
        c.put("a", 1)
        c.put("b", 2)
        _ = "a" in c          # peek a; should NOT change recency
        c.put("c", 3)
        assert "a" not in c, (
            "containment check should not refresh recency; "
            "a was LRU and should have been evicted"
        )
        assert "b" in c
        assert "c" in c

    tests = [
        ("class_exists",                      t_class_exists),
        ("init_rejects_zero_capacity",        t_init_rejects_zero_capacity),
        ("init_rejects_negative_capacity",    t_init_rejects_negative_capacity),
        ("get_missing_raises_key_error",      t_get_missing_raises_key_error),
        ("len_initial_zero",                  t_len_initial_zero),
        ("len_grows_to_capacity",             t_len_grows_to_capacity),
        ("capacity_one_eviction",             t_capacity_one_eviction),
        ("update_existing_key_does_not_grow", t_update_existing_key_does_not_grow),
        ("get_refreshes_recency",             t_get_refreshes_recency),
        ("contains_does_not_touch_recency",   t_contains_does_not_touch_recency),
    ]

    results = []
    passed = 0
    for name, fn in tests:
        ok, detail = _run_test(name, fn)
        results.append({"name": name, "passed": ok, "detail": detail})
        passed += int(ok)
        status = "OK" if ok else "FAIL"
        print(f"  {name:<40} [{status}]" + (f"  {detail}" if not ok else ""))

    pct = 100.0 * passed / len(tests)
    print(f"Summary: Passed: {passed}/{len(tests)} ({pct:.1f}%)")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "module": f"{LRUClass.__module__}.{LRUClass.__name__}",
            "tests": results,
            "passed": passed,
            "total": len(tests),
            "pass_pct": pct,
        }, indent=2))

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
