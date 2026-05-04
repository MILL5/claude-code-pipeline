"""Locate the pipeline-produced base64 module.

The pipeline is free to name its module anything (src/base64encoder.py, src/encoding/b64.py, etc.).
The fixtures here import via discovery rather than a hardcoded name so the benchmark doesn't
penalize naming choices.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any


def _candidate_modules(src_root: Path) -> list[Path]:
    """All .py files under src/ except __init__ stubs."""
    out: list[Path] = []
    for p in src_root.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        out.append(p)
    return out


def _load_module_from_path(path: Path, src_root: Path) -> Any | None:
    rel = path.relative_to(src_root).with_suffix("")
    mod_name = "src." + ".".join(rel.parts)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def _looks_like_base64_module(mod: Any) -> bool:
    enc = getattr(mod, "encode", None)
    dec = getattr(mod, "decode", None)
    if not callable(enc) or not callable(dec):
        return False
    try:
        enc_sig = inspect.signature(enc)
        dec_sig = inspect.signature(dec)
    except (ValueError, TypeError):
        return False
    return len(enc_sig.parameters) == 1 and len(dec_sig.parameters) == 1


def discover(project_root: Path) -> Any:
    """Return the discovered base64 module, or raise ImportError."""
    src_root = project_root / "src"
    if not src_root.is_dir():
        raise ImportError(f"src/ does not exist under {project_root}")

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    for path in _candidate_modules(src_root):
        mod = _load_module_from_path(path, src_root)
        if mod is not None and _looks_like_base64_module(mod):
            return mod

    raise ImportError(
        "No module under src/ exposes encode(x) and decode(x) with the expected signature. "
        "The pipeline did not produce a recognizable base64 module."
    )
