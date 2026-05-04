# Feature Request: base64 module

Please add a base64 encoder/decoder to this Python project.

## Requirements

- Implement standard base64 encoding and decoding per RFC 4648 (the standard alphabet, with `+` and `/`, padding with `=`).
- Provide two top-level functions in a module under `src/`:
  - `encode(data: bytes) -> str` — encodes raw bytes to a base64 string
  - `decode(text: str) -> bytes` — decodes a base64 string back to raw bytes
- Add a small CLI (`python -m <module>`) with two subcommands:
  - `encode <file>` — reads the file as bytes, prints base64 to stdout
  - `decode <file>` — reads the file as base64 text, prints raw bytes to stdout
- Decoding should raise `ValueError` with a clear message for malformed input (bad characters, wrong padding, etc.).
- Empty input should round-trip cleanly: `encode(b"") == ""` and `decode("") == b""`.
- Include unit tests covering normal and edge cases.

## Out of scope

- URL-safe base64 (the `_-` alphabet variant) — not needed.
- Streaming / chunked APIs — single-call functions are fine.
- Custom alphabets or padding schemes.

## Implementation note

Do **not** import `base64` from the Python standard library to do the work. Implement the encoding/decoding using bit operations against the standard alphabet. This is intentional — the project exists to measure what is produced from scratch.
