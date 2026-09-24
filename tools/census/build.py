#!/usr/bin/env python3
"""Deterministic build for the census tool unit.

Builds ``dist/census-0.1.0.pyz`` from ``census/**`` + ``../common/toolkit/**``
(plus a generated ``__main__.py``), then runs the built artifact's
``--describe`` and writes ``TOOL.json`` and ``dist/census-0.1.0.pyz.sha256``.

Twice-built artifacts from identical sources are byte-identical.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMON = HERE.parent / "common"
sys.path.insert(0, str(COMMON))

from build_zipapp import build_zipapp, collect_tree, entry_py  # noqa: E402
from toolkit import canonical_json, tool_unit  # noqa: E402

VERSION = "0.1.0"
ARTIFACT = HERE / "dist" / f"census-{VERSION}.pyz"


def main() -> int:
    files = {
        "__main__.py": entry_py("census.cli"),
        **collect_tree(HERE / "census", prefix="census"),
        **collect_tree(COMMON / "toolkit", prefix="toolkit"),
    }
    sha = build_zipapp(files, ARTIFACT)
    proc = subprocess.run(
        [sys.executable, str(ARTIFACT), "--describe"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    described = canonical_json.canonical_loads(proc.stdout)
    tool_json = tool_unit.tool_json_bytes(
        described,
        artifact_file=f"dist/{ARTIFACT.name}",
        artifact_sha256=sha,
        artifact_size=ARTIFACT.stat().st_size,
    )
    (HERE / "TOOL.json").write_bytes(tool_json)
    (ARTIFACT.with_name(ARTIFACT.name + ".sha256")).write_text(
        f"{sha}  {ARTIFACT.name}\n", encoding="ascii"
    )
    print(f"built {ARTIFACT.relative_to(HERE)} sha256={sha} size={ARTIFACT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
