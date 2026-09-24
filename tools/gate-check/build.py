#!/usr/bin/env python3
"""Build the deterministic gate-check artifact and write its TOOL.json pin.

    python3 build.py [--out-dir DIR] [--tool-json PATH]

Writes ``<out-dir>/gate-check-0.1.0.pyz`` (+ ``.sha256``) and ``TOOL.json``.
The artifact is a pure function of the sources, so rebuilding yields identical
bytes and therefore an identical ``TOOL.json``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

UNIT = Path(__file__).resolve().parent
COMMON = UNIT.parent / "common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))

from build_zipapp import build_zipapp, collect_tree, entry_py  # noqa: E402
from toolkit import canonical_json, tool_unit  # noqa: E402

NAME = "gate-check"
VERSION = "0.1.0"
ARTIFACT_NAME = f"{NAME}-{VERSION}.pyz"


def build(*, out_dir: Path | None = None, tool_json_path: Path | None = None,
          quiet: bool = False) -> dict:
    out_dir = Path(out_dir) if out_dir is not None else UNIT / "dist"
    tool_json_path = Path(tool_json_path) if tool_json_path is not None else UNIT / "TOOL.json"
    files = {
        "__main__.py": entry_py("gate_check.cli"),
        **collect_tree(UNIT / "gate_check", prefix="gate_check"),
        **collect_tree(COMMON / "toolkit", prefix="toolkit"),
    }
    artifact = out_dir / ARTIFACT_NAME
    sha = build_zipapp(files, artifact)

    proc = subprocess.run(
        [sys.executable, str(artifact), "--describe"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"built artifact --describe failed rc={proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace')}"
        )
    described = canonical_json.canonical_loads(proc.stdout)
    tool_json = tool_unit.tool_json_bytes(
        described,
        artifact_file=f"dist/{ARTIFACT_NAME}",
        artifact_sha256=sha,
        artifact_size=artifact.stat().st_size,
    )
    tool_json_path.parent.mkdir(parents=True, exist_ok=True)
    tool_json_path.write_bytes(tool_json)
    sha_path = out_dir / (ARTIFACT_NAME + ".sha256")
    sha_path.write_bytes(f"{sha}  dist/{ARTIFACT_NAME}\n".encode("ascii"))

    summary = {
        "artifact": str(artifact),
        "sha256": sha,
        "size": artifact.stat().st_size,
        "tool_json": str(tool_json_path),
        "tool_json_sha256": tool_unit.sha256_file(tool_json_path),
    }
    if not quiet:
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build.py", description=__doc__)
    parser.add_argument("--out-dir", default=None, help="artifact output directory")
    parser.add_argument("--tool-json", default=None, help="TOOL.json output path")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    build(
        out_dir=Path(args.out_dir) if args.out_dir else None,
        tool_json_path=Path(args.tool_json) if args.tool_json else None,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
