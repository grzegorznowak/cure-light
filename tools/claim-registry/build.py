#!/usr/bin/env python3
"""Build the deterministic claim-registry tool unit (``.pyz`` + ``TOOL.json``).

Run from the unit root::

    python3 build.py

Writes:

* ``dist/claim-registry-0.2.0.pyz``       deterministic zipapp
* ``dist/claim-registry-0.2.0.pyz.sha256`` ``"<sha256>  <artifact filename>\\n"``
* ``TOOL.json``                           describe payload + artifact pin block

Same sources -> same artifact bytes -> same sha256.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

UNIT_ROOT = Path(__file__).resolve().parent
COMMON = UNIT_ROOT.parent / "common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))

from build_zipapp import build_zipapp, collect_tree, entry_py  # noqa: E402
from toolkit import tool_unit  # noqa: E402

from claim_registry.tool_manifest import MANIFEST  # noqa: E402


def main() -> int:
    dist = UNIT_ROOT / "dist"
    files = {
        "__main__.py": entry_py("claim_registry.cli"),
        **collect_tree(UNIT_ROOT / "claim_registry", prefix="claim_registry"),
        **collect_tree(COMMON / "toolkit", prefix="toolkit"),
    }
    out = dist / f"{MANIFEST['name']}-{MANIFEST['version']}.pyz"
    sha = build_zipapp(files, out)
    size = out.stat().st_size

    # Probe the built artifact exactly as an agent would: --describe must work
    # standalone and must reproduce the source MANIFEST byte-for-byte.
    proc = subprocess.run(
        [sys.executable, str(out), "--describe"], capture_output=True
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
        return 1
    described = json.loads(proc.stdout)
    if tool_unit.describe_bytes(described) != tool_unit.describe_bytes(MANIFEST):
        sys.stderr.write(
            "error: built artifact --describe differs from the source MANIFEST\n"
        )
        return 1

    artifact_file = f"dist/{out.name}"
    tool_json = tool_unit.tool_json_bytes(
        MANIFEST,
        artifact_file=artifact_file,
        artifact_sha256=sha,
        artifact_size=size,
    )
    (UNIT_ROOT / "TOOL.json").write_bytes(tool_json)
    (dist / f"{out.name}.sha256").write_bytes(f"{sha}  {out.name}\n".encode("utf-8"))

    print(f"built {artifact_file} sha256={sha} size={size}")
    print(f"wrote TOOL.json and dist/{out.name}.sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
