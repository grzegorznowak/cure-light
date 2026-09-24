"""Deterministic single-artifact (.pyz) builder for cure-light tool units.

``build_zipapp`` writes a zipapp whose bytes are a pure function of the input
files: entries sorted by arcname, ``ZIP_STORED`` (no compression), fixed
1980-01-01 timestamps, fixed external attributes, fixed shebang.  Rebuilding
the same sources always yields the same sha256, which is what makes the
``TOOL.json`` artifact pin meaningful.

Usage from a unit ``build.py``::

    from build_zipapp import build_zipapp, collect_tree, entry_py

    files = {
        "__main__.py": entry_py("claim_registry.cli"),
        **collect_tree("claim_registry", prefix="claim_registry"),
        **collect_tree("../common/toolkit", prefix="toolkit"),
    }
    sha = build_zipapp(files, dist / "claim-registry-0.2.0.pyz")
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path
from typing import Mapping

_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_SHEBANG = b"#!/usr/bin/env python3\n"


def _as_bytes(data) -> bytes:
    """bytes/str are literal content; Path objects are read from disk."""
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, Path):
        return data.read_bytes()
    if isinstance(data, str):
        return data.encode("utf-8")
    raise TypeError(f"unsupported file payload: {type(data)!r}")


def _check_arcname(arcname: str) -> None:
    if not arcname or arcname.startswith("/") or ".." in Path(arcname).parts:
        raise ValueError(f"invalid archive member name: {arcname!r}")


def build_zipapp(files: Mapping[str, object], out_path: str | Path) -> str:
    """Build the .pyz at ``out_path``; returns the artifact sha256."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    items = sorted(files.items(), key=lambda kv: kv[0])
    for arcname, _ in items:
        _check_arcname(arcname)
    tmp = out.with_name(out.name + ".tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(_SHEBANG)
            with zipfile.ZipFile(fh, "w", compression=zipfile.ZIP_STORED) as zf:
                for arcname, payload in items:
                    info = zipfile.ZipInfo(arcname, date_time=_FIXED_DATE_TIME)
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o644 << 16
                    zf.writestr(info, _as_bytes(payload))
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()
    return sha256_file(out)


def collect_tree(root: str | Path, *, prefix: str = "", skip_dirs=("__pycache__",)) -> dict[str, Path]:
    """Map ``arcname -> path`` for every file under ``root`` (sorted)."""
    root = Path(root)
    files: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix == ".pyc":
            continue
        rel = path.relative_to(root).as_posix()
        arcname = f"{prefix}/{rel}" if prefix else rel
        files[arcname] = path
    return files


def entry_py(import_path: str, func: str = "main") -> str:
    """Generate the ``__main__.py`` that dispatches into a unit's CLI."""
    return f"from {import_path} import {func}\nraise SystemExit({func}())\n"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
