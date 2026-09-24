"""Command line interface for the gate-check tool unit.

    gate-check check --manifest M.json [--registry R.json] [--report V.json]
                     [--captures DIR] [--proposals P.json] [--windows W.json]
                     [--tool-manifest TOOL.json] [--artifact PATH]
                     [--base-dir DIR] [--report-out OUT.json]
    gate-check --describe | --check-pin SHA
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from toolkit import canonical_json
from toolkit import tool_unit

from . import checks

DESCRIBE = tool_unit.build_manifest(
    name="gate-check",
    version="0.1.0",
    summary=(
        "Mechanical permission gate for a completed claim-registry run: "
        "re-verifies the claim-run-manifest/1, registry bytes/hashes/witness, "
        "validation report, capture identities and tool pin."
    ),
    dependencies=[],
    commands={
        "check": {
            "usage": (
                "gate-check check --manifest M.json [--registry R.json] "
                "[--report V.json] [--captures DIR] [--proposals P.json] "
                "[--windows W.json] [--tool-manifest TOOL.json] "
                "[--artifact PATH] [--base-dir DIR] [--report-out OUT.json]"
            ),
            "summary": (
                "Verify a claim-run-manifest/1 and every recorded artifact; "
                "exit 0 only when all mechanical checks pass."
            ),
            "params": [
                {"name": "--manifest", "type": "path", "required": True,
                 "default": None,
                 "description": "canonical claim-run-manifest/1 JSON"},
                {"name": "--registry", "type": "path", "required": False,
                 "default": None, "description": "override the manifest registry path"},
                {"name": "--report", "type": "path", "required": False,
                 "default": None, "description": "override the manifest validation-report path"},
                {"name": "--captures", "type": "path", "required": False,
                 "default": None, "description": "override the capture directory"},
                {"name": "--proposals", "type": "path", "required": False,
                 "default": None, "description": "override the proposals file path"},
                {"name": "--windows", "type": "path", "required": False,
                 "default": None, "description": "override the window manifests path"},
                {"name": "--tool-manifest", "type": "path", "required": False,
                 "default": None, "description": "TOOL.json pin of the producer"},
                {"name": "--artifact", "type": "path", "required": False,
                 "default": None, "description": "producer artifact to hash"},
                {"name": "--base-dir", "type": "path", "required": False,
                 "default": None,
                 "description": "base for manifest-relative paths (default: manifest dir)"},
                {"name": "--report-out", "type": "path", "required": False,
                 "default": None, "description": "also write the report here"},
            ],
            "outputs": {
                "stdout": "gate-check-report/1 canonical JSON",
                "--report-out": "same report as canonical bytes (no trailing newline)",
            },
            "exit_codes": {
                "0": "all checks passed; finalized_unclaimed permission granted",
                "1": "at least one check failed; read report.errors",
                "2": "usage/environment: missing/malformed manifest or unreadable override path",
            },
        }
    },
    recipe_pins={
        "run_manifest_schema": checks.RUN_MANIFEST_SCHEMA,
        "gate_report_schema": checks.GATE_REPORT_SCHEMA,
    },
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate-check",
        description="Mechanical permission gate for a completed claim-registry run.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check", help="verify a run manifest and its artifacts")
    p.add_argument("--manifest", required=True, help="canonical claim-run-manifest/1 JSON")
    p.add_argument("--registry", default=None, help="override registry path")
    p.add_argument("--report", default=None, help="override validation report path")
    p.add_argument("--captures", default=None, help="override capture directory")
    p.add_argument("--proposals", default=None, help="override proposals file path")
    p.add_argument("--windows", default=None, help="override window manifests path")
    p.add_argument("--tool-manifest", default=None, help="TOOL.json pin")
    p.add_argument("--artifact", default=None, help="producer artifact path")
    p.add_argument("--base-dir", default=None,
                   help="base dir for manifest-relative paths (default: manifest dir)")
    p.add_argument("--report-out", default=None, help="write the report here as well")
    p.set_defaults(func=cmd_check)
    return parser


def cmd_check(args: argparse.Namespace) -> int:
    report = checks.run_check(
        manifest_path=Path(args.manifest),
        base_dir=Path(args.base_dir) if args.base_dir else None,
        registry_override=Path(args.registry) if args.registry else None,
        report_override=Path(args.report) if args.report else None,
        captures_override=Path(args.captures) if args.captures else None,
        proposals_override=Path(args.proposals) if args.proposals else None,
        windows_override=Path(args.windows) if args.windows else None,
        tool_manifest_override=Path(args.tool_manifest) if args.tool_manifest else None,
        artifact_override=Path(args.artifact) if args.artifact else None,
    )
    data = canonical_json.canonical_dumps(report)
    if args.report_out:
        out = Path(args.report_out)
        if out.parent and str(out.parent):
            out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    sys.stdout.buffer.write(data + b"\n")
    sys.stdout.buffer.flush()
    return 0 if report["valid"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    code = tool_unit.run_describe(DESCRIBE, args)
    if code is not None:
        return code
    parser = build_parser()
    parsed = parser.parse_args(args)
    try:
        return parsed.func(parsed)
    except tool_unit.UsageError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return tool_unit.EXIT_USAGE
    except BrokenPipeError:  # pragma: no cover - defensive
        return tool_unit.EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
