"""Locate the pipeline-produced LRUCache class.

The pipeline is free to name its module anything (src/lru.py, src/cache/lru_cache.py,
etc.) and free to name the class anything that looks like an LRU cache. The
fixtures here import via discovery rather than a hardcoded name so the benchmark
doesn't penalize naming choices.

Discovery rule: under src/, find a class whose `__init__` accepts at least one
positional argument (capacity) and which exposes both `get` and `put` methods.
"""

from __future__ import annotations

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


def _looks_like_lru_class(cls: Any) -> bool:
    if not inspect.isclass(cls):
        return False
    if not (callable(getattr(cls, "get", None)) and callable(getattr(cls, "put", None))):
        return False
    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError):
        return False
    params = [
        p for p in sig.parameters.values()
        if p.name != "self" and p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    # __init__ should accept at least a capacity positional arg.
    return len(params) >= 1


def discover(project_root: Path) -> type:
    """Return the discovered LRUCache class, or raise ImportError."""
    src_root = project_root / "src"
    if not src_root.is_dir():
        raise ImportError(f"src/ does not exist under {project_root}")

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    for path in _candidate_modules(src_root):
        mod = _load_module_from_path(path, src_root)
        if mod is None:
            continue
        for name in dir(mod):
            if name.startswith("_"):
                continue
            obj = getattr(mod, name)
            # Only accept classes defined in this module (not re-exported stdlib).
            if _looks_like_lru_class(obj) and getattr(obj, "__module__", "") == mod.__name__:
                return obj

    raise ImportError(
        "No class under src/ has the shape of an LRU cache "
        "(class with get/put methods and __init__ accepting capacity). "
        "The pipeline did not produce a recognizable LRU cache."
    )
