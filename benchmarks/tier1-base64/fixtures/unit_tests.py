"""Unit + functional tests for the pipeline-produced base64 module.

Run from the project root:
    python3 fixtures/unit_tests.py [--project=PATH]

Exit codes:
    0 — all tests pass
    1 — at least one failed
    2 — module not discoverable
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
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
        mod = discover(project)
    except ImportError as e:
        print(f"DISCOVERY FAILED: {e}")
        if args.json:
            Path(args.json).write_text(json.dumps({"error": "discovery_failed", "detail": str(e)}))
        return 2

    # The module exposing encode/decode (e.g. "src.b64")
    mod_dotted = mod.__name__
    # The CLI is more idiomatically invoked as `python -m <package>`. Pick the
    # parent package as the preferred CLI target, fall back to the module itself.
    parent_pkg = mod_dotted.rsplit(".", 1)[0] if "." in mod_dotted else mod_dotted
    cli_candidates = [parent_pkg, mod_dotted] if parent_pkg != mod_dotted else [mod_dotted]

    def _try_cli(args: list[str], binary_stdout: bool = False) -> tuple[int, bytes, str, str]:
        """Try each CLI candidate; return (exit_code, stdout_bytes, stderr_text, used_target)."""
        last_proc = None
        for target in cli_candidates:
            proc = subprocess.run(
                [sys.executable, "-m", target] + args,
                cwd=project, capture_output=True, timeout=15,
            )
            last_proc = (proc, target)
            err_text = proc.stderr.decode("utf-8", errors="replace")
            err_low = (err_text + proc.stdout.decode("utf-8", errors="replace")).lower()
            if "no module named" in err_low or "modulenotfounderror" in err_low:
                continue
            return proc.returncode, proc.stdout, err_text, target
        if last_proc:
            proc, target = last_proc
            return (
                proc.returncode,
                proc.stdout,
                proc.stderr.decode("utf-8", errors="replace"),
                target,
            )
        return 1, b"", "no CLI candidates", ""

    def t_module_exists() -> None:
        assert mod is not None

    def t_decode_rejects_bad_chars() -> None:
        try:
            mod.decode("!@#$%^&*")
        except ValueError:
            return
        except Exception as e:
            raise AssertionError(f"expected ValueError, got {type(e).__name__}: {e}") from e
        raise AssertionError("expected ValueError, no exception raised")

    def t_decode_rejects_bad_padding() -> None:
        try:
            mod.decode("abc")  # length not multiple of 4, no padding
        except ValueError:
            return
        except Exception as e:
            raise AssertionError(f"expected ValueError, got {type(e).__name__}: {e}") from e
        raise AssertionError("expected ValueError, no exception raised")

    def t_known_vector_hello() -> None:
        # "hello" -> "aGVsbG8="
        assert mod.encode(b"hello") == "aGVsbG8=", f"got {mod.encode(b'hello')!r}"
        assert mod.decode("aGVsbG8=") == b"hello"

    def t_known_vector_pad1() -> None:
        # 2-byte input -> 1 char of padding
        assert mod.encode(b"hi") == "aGk=", f"got {mod.encode(b'hi')!r}"

    def t_known_vector_pad2() -> None:
        # 1-byte input -> 2 chars of padding
        assert mod.encode(b"f") == "Zg==", f"got {mod.encode(b'f')!r}"

    def t_cli_module_invocable() -> None:
        # `python -m <pkg>` should at least not crash with import errors.
        rc, out, err, target = _try_cli([])
        combined = (out.decode("utf-8", errors="replace") + err).lower()
        assert "no module named" not in combined and "modulenotfounderror" not in combined, (
            f"none of {cli_candidates} are runnable CLIs: {combined[:200]}"
        )

    def t_cli_encode_decode_round_trip() -> None:
        original = b"benchmark-content-\x00\x01\x02\xff"
        with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
            f.write(original)
            input_path = f.name
        try:
            rc, out, err, target = _try_cli(["encode", input_path])
            if rc != 0:
                raise AssertionError(f"CLI encode exited {rc} (target={target}): {err[:200]}")
            encoded = out.decode("ascii", errors="replace").strip()
            assert encoded, f"CLI encode produced empty output (target={target})"

            with tempfile.NamedTemporaryFile(delete=False, mode="w") as f2:
                f2.write(encoded)
                enc_path = f2.name

            rc2, out2, err2, target2 = _try_cli(["decode", enc_path])
            if rc2 != 0:
                raise AssertionError(f"CLI decode exited {rc2} (target={target2}): {err2[:200]}")
            # Trim a single trailing newline if the CLI added one (common with `print()`)
            decoded = out2[:-1] if out2.endswith(b"\n") and out2[:-1] == original else out2
            assert decoded == original, (
                f"CLI round-trip mismatch: got {decoded!r}, expected {original!r} (target={target2})"
            )
        finally:
            try:
                os.unlink(input_path)
            except OSError:
                pass

    tests = [
        ("module_exists",                 t_module_exists),
        ("decode_rejects_bad_chars",      t_decode_rejects_bad_chars),
        ("decode_rejects_bad_padding",    t_decode_rejects_bad_padding),
        ("known_vector_hello",            t_known_vector_hello),
        ("known_vector_pad1",             t_known_vector_pad1),
        ("known_vector_pad2",             t_known_vector_pad2),
        ("cli_module_invocable",          t_cli_module_invocable),
        ("cli_round_trip",                t_cli_encode_decode_round_trip),
    ]

    results = []
    passed = 0
    for name, fn in tests:
        ok, detail = _run_test(name, fn)
        results.append({"name": name, "passed": ok, "detail": detail})
        passed += int(ok)
        status = "OK" if ok else "FAIL"
        print(f"  {name:<32} [{status}]" + (f"  {detail}" if not ok else ""))

    pct = 100.0 * passed / len(tests)
    print(f"Summary: Passed: {passed}/{len(tests)} ({pct:.1f}%)")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "module": mod_dotted,
            "tests": results,
            "passed": passed,
            "total": len(tests),
            "pass_pct": pct,
        }, indent=2))

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
