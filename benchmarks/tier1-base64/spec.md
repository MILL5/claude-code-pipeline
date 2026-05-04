# Acceptance Spec: tier1-base64

This spec is **not** given to the pipeline. It is the scorer's contract — what "correct output" means.

## Functional contract

- An importable Python module exists under `src/` exposing `encode(bytes) -> str` and `decode(str) -> bytes`.
- A CLI is invocable as `python -m <module>` with `encode <file>` and `decode <file>` subcommands.

## Property contract (the oracle)

For arbitrary byte strings `x`:

1. **Round-trip:** `decode(encode(x)) == x` for all `x` (including empty bytes, all-zero bytes, all-0xFF bytes, lengths 1..256).
2. **Output validity:** `encode(x)` consists only of characters in the standard base64 alphabet (`A-Za-z0-9+/=`).
3. **Padding correctness:** `len(encode(x)) % 4 == 0` for all `x`; padding `=` only appears at the end.
4. **Empty round-trip:** `encode(b"") == ""` and `decode("") == b""`.
5. **Reference equivalence:** `encode(x)` matches Python's stdlib `base64.b64encode(x).decode("ascii")` for all `x`.

## Negative contract

- `decode` raises `ValueError` (not a generic `Exception`) on:
  - Strings containing non-alphabet characters (e.g., `"!@#$"`).
  - Strings with invalid padding (e.g., `"abc"` — length not a multiple of 4 with no padding).

## Scoring weights

| Component | Weight |
|-----------|--------|
| Property tests (round-trip + validity + padding + empty + reference) | 0.5 |
| Unit tests (negative cases, CLI smoke) | 0.2 |
| Functional contract (module exists, CLI exists) | 0.3 |

Composite correctness = weighted average of pass percentages.

## Out of scope (not penalized if absent)

- URL-safe variant
- Streaming / chunked APIs
- Performance optimizations
- Type stub files
