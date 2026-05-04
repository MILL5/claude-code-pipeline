# Feature Request: base64 module

Please add a base64 encoder/decoder to this Python project.

> **Benchmark mode — no clarifying questions.** This request is the frozen input
> for the Tier 1 regression benchmark. Every potentially-ambiguous decision is
> pre-specified below in the `Decisions` section. **Architect 1a must not ask
> clarifying questions** — proceed directly to spec finalization (1a-spec.md) and
> on to planning (1b). If a corner case is not explicitly decided here, choose the
> most idiomatic Python answer and document it in 1a-spec.md without halting.

## Requirements

- Implement standard base64 encoding and decoding per RFC 4648 (the standard
  alphabet, with `+` and `/`, padding with `=`).
- Provide two top-level functions in a module under `src/`:
  - `encode(data: bytes) -> str` — encodes raw bytes to a base64 string
  - `decode(text: str) -> bytes` — decodes a base64 string back to raw bytes
- Add a small CLI (`python -m <package>`) with two subcommands:
  - `encode <file>` — reads the file as bytes, writes base64 to stdout
  - `decode <file>` — reads the file as base64 text, writes raw bytes to stdout
- Decoding raises `ValueError` (not a generic `Exception`) with a clear message
  for malformed input.
- Empty input round-trips: `encode(b"") == ""` and `decode("") == b""`.
- Include unit tests covering normal and edge cases.

## Out of scope

- URL-safe base64 (the `_-` alphabet variant) — not needed.
- Streaming / chunked APIs — single-call functions are fine.
- Custom alphabets or padding schemes.

## Implementation note

Do **not** import `base64` from the Python standard library to do the work.
Implement the encoding/decoding using bit operations against the standard
alphabet. This is intentional — the project exists to measure what is produced
from scratch.

## Decisions (frozen — do not re-ask)

These resolve the ambiguities Architect 1a would otherwise surface. Treat as
final.

### Module layout

- **Module name:** `b64`. The implementation lives at `src/b64.py` and exports
  `encode` and `decode` as top-level functions.
- **CLI module:** `src/__main__.py`. CLI is invoked as `python -m src` (the
  `src` package's `__main__.py` parses argv and dispatches to `b64.encode` /
  `b64.decode`).
- **Package init:** `src/__init__.py` may stay empty or re-export `encode` /
  `decode` — implementation choice.

### CLI behavior

- **`encode <file>` output:** Print the base64 string followed by a single
  trailing newline (use `print(...)`).
- **`decode <file>` output:** Write **raw bytes** to stdout via
  `sys.stdout.buffer.write(...)`. Do **not** print the bytes' repr. Do **not**
  add a trailing newline (the decoded payload is opaque).
- **`decode` input:** Read the file contents, then call `.strip()` on the text
  to drop a single leading/trailing newline only. **Inner whitespace is not
  tolerated** — any non-alphabet, non-padding character (including spaces,
  `\r`, `\n`) inside the body causes `decode()` to raise `ValueError`. (This
  keeps the property tests deterministic.)
- **Argument parsing:** Implementation choice — `argparse` or hand-rolled
  `sys.argv` are both acceptable.
- **Missing/invalid arguments:** Print a short usage line to stderr and exit
  with a non-zero code. Specific exit code is implementation choice.

### Error handling

- `decode()` raises `ValueError` with a descriptive message for:
  - Length not a multiple of 4 (after any stripping).
  - Non-alphabet characters in the body.
  - Padding (`=`) appearing anywhere except at the end.
  - More than 2 `=` characters.
- File-not-found / file-IO errors propagate naturally — no special handling
  required.

### Tests

- **Coverage:** Thorough case coverage is required; no numeric coverage floor.
- **Test files:** Place at project root as `test_b64.py` (and `test_cli.py` if
  CLI tests are split out). Pytest is already configured.
- **Tests must cover:** known RFC 4648 vectors, empty input, 1-byte and 2-byte
  inputs (padding edge cases), invalid characters, invalid padding length,
  invalid padding position.

### Type hints / style

- Type hints required on all public function signatures (`encode`, `decode`,
  CLI `main`).
- Mypy strict is enabled — avoid `Any` in public APIs.
- Brief one-line docstrings on `encode` and `decode`. No multi-paragraph
  docstrings.
