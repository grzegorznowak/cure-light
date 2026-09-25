"""Thin CLI for the claim-registry pilot producer.

Commands: ``capture``, ``frame``, ``assemble``, ``validate``, ``windows``,
``hash``, ``manifest``.  Run from the unit root::

    python3 -m claim_registry.cli --help

``--describe`` and ``--check-pin SHA`` are handled before argparse through
:func:`toolkit.tool_unit.run_describe`; they work without the pinned
tree-sitter dependencies so an agent can learn what to install.

Exit codes: 0 ok; 1 semantic/validation failure (messages name the exact
unit_id/field; ``validate`` reports carry ``report.errors``); 2 usage/environment
(bad arguments, missing/unreadable files, missing or wrong pinned dependency).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from . import canonical

# Importing tool_manifest first also makes ``../common`` importable in a dev
# checkout (the packaged .pyz bundles toolkit/).
from .tool_manifest import MANIFEST
from toolkit import tool_unit

CAPTURE_MANIFEST = "capture-manifest/1"
RUN_MANIFEST_SCHEMA = "claim-run-manifest/1"
PROPOSALS_SCHEMA_VERSION = "claim-proposals/1"

#: Mirrors claim_registry.registry.DEFAULT_WINDOW_RECIPE; kept as literals so
#: that --describe/--help never import the tree-sitter walker.
WINDOW_MAX_UNITS = 64
WINDOW_MAX_BYTES = 65536
WINDOW_OVERLAP_UNITS = 8

#: Mirrors claim_label_contract.slicing defaults (literals for --describe).
FRAME_SLICE_MAX_BYTES = 16384
FRAME_SLICE_MAX_UNITS = 80
FRAME_SLICE_MAX_INPUT_BYTES = 65536
FRAME_SLICE_OVERLAP_UNITS = 4
FRAME_SLICE_MAX_SLICES = 32


class SemanticError(Exception):
    """Semantic/validation failure -> exit 1 (actionable message)."""


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _write_bytes(path: str, data: bytes) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def write_capture_dir(captures: Sequence, outdir: str) -> str:
    rawdir = os.path.join(outdir, "raw")
    os.makedirs(rawdir, exist_ok=True)
    records = []
    for i, cap in enumerate(captures):
        name = f"{i:04d}.bin"
        _write_bytes(os.path.join(rawdir, name), cap.data)
        record = cap.record()
        record["file"] = f"raw/{name}"
        records.append(record)
    manifest = {"schema_version": CAPTURE_MANIFEST, "sources": records}
    manifest_path = os.path.join(outdir, "manifest.json")
    _write_bytes(manifest_path, canonical.canonical_dumps(manifest))
    return manifest_path


def read_capture_dir(indir: str) -> list:
    from .capture import SourceCapture, verify_capture

    manifest_path = os.path.join(indir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise tool_unit.UsageError(
            f"capture directory {indir!r} has no manifest.json"
        )
    manifest = canonical.canonical_loads(_read_bytes(manifest_path))
    if manifest.get("schema_version") != CAPTURE_MANIFEST:
        raise SemanticError(
            f"unsupported capture manifest version "
            f"{manifest.get('schema_version')!r} in {manifest_path}"
        )
    captures = []
    for record in manifest.get("sources", []):
        rel = record.get("file")
        if not isinstance(rel, str) or not rel:
            raise SemanticError(
                f"capture manifest {manifest_path}: source record "
                f"{record.get('source_ref')!r} has no file"
            )
        raw_path = os.path.join(indir, rel)
        if not os.path.isfile(raw_path):
            raise tool_unit.UsageError(
                f"capture raw file missing: {raw_path} "
                f"(source {record.get('source_ref')!r})"
            )
        data = _read_bytes(raw_path)
        failures = verify_capture(record, data)
        if failures:
            raise SemanticError(
                f"capture {record.get('source_ref')} failed verification: {failures}"
            )
        cap = SourceCapture(
            locator=record["locator"],
            source_class=record["class"],
            data=data,
            pointer_ref=record.get("pointer_ref"),
            interpretation_ref=record.get("interpretation_ref"),
        )
        if cap.source_ref != record.get("source_ref"):
            raise SemanticError(
                f"capture source_ref mismatch: manifest {record.get('source_ref')} "
                f"recomputed {cap.source_ref}"
            )
        captures.append(cap)
    return captures


def _print_json(value) -> None:
    sys.stdout.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _aligned_metadata(values, flag: str, count: int, default):
    """Align a once/per-source metadata flag against the source count."""
    if not values:
        return [default] * count
    if len(values) == 1:
        return list(values) * count
    if len(values) == count:
        return list(values)
    raise tool_unit.UsageError(
        f"capture: {flag} given {len(values)} time(s) for {count} source(s); "
        f"pass {flag} once (applies to every source) or once per source"
    )


def cmd_capture(args: argparse.Namespace) -> int:
    """Capture one or more sources into a single capture manifest (batch)."""
    from .capture import capture_file

    inputs = list(args.input)
    locators = list(args.locator)
    if len(locators) != len(inputs):
        raise tool_unit.UsageError(
            f"capture: --in given {len(inputs)} time(s) but --locator given "
            f"{len(locators)}; pass one --in/--locator pair per source"
        )
    classes = _aligned_metadata(args.source_class, "--class", len(inputs), "api-document")
    pointer_refs = _aligned_metadata(args.pointer_ref, "--pointer-ref", len(inputs), None)
    interpretation_refs = _aligned_metadata(
        args.interpretation_ref, "--interpretation-ref", len(inputs), None
    )

    seen: dict[str, str] = {}
    captures = []
    for path, locator, source_class, pointer_ref, interpretation_ref in zip(
        inputs, locators, classes, pointer_refs, interpretation_refs
    ):
        if locator in seen:
            raise tool_unit.UsageError(
                f"capture: duplicate locator {locator!r} "
                f"(--in {seen[locator]!r} and {path!r})"
            )
        seen[locator] = path
        captures.append(capture_file(
            path,
            locator,
            source_class=source_class,
            pointer_ref=pointer_ref,
            interpretation_ref=interpretation_ref,
        ))

    manifest_path = os.path.join(args.out, "manifest.json")
    if os.path.exists(manifest_path):
        raise tool_unit.UsageError(
            f"capture: {args.out!r} already contains manifest.json; refusing to "
            "overwrite an existing capture (use a fresh --out directory)"
        )
    manifest_path = write_capture_dir(captures, args.out)
    if len(captures) == 1:
        _print_json({"manifest": manifest_path, "source": captures[0].record()})
    else:
        _print_json({
            "manifest": manifest_path,
            "sources": [cap.record() for cap in captures],
        })
    return tool_unit.EXIT_OK


def cmd_frame(args: argparse.Namespace) -> int:
    from .capture import SourceCapture
    from .frame import frame_source

    data = _read_bytes(args.input)
    if args.source_ref:
        source_ref = args.source_ref
    elif args.locator:
        cap = SourceCapture(
            locator=args.locator,
            source_class="in-diff-file",
            data=data,
        )
        source_ref = cap.source_ref
    else:
        raise tool_unit.UsageError("frame requires --locator or --source-ref")
    frame = frame_source(data)
    out = {
        "source_ref": source_ref,
        "source_length": frame.source_length,
        "unit_count": frame.unit_count,
        "block_count": frame.block_count,
        "separator_count": frame.separator_count,
        "recipe": frame.recipe,
        "units": [u.record(source_ref) for u in frame.units],
    }
    payload = json.dumps(out, indent=2, ensure_ascii=False).encode("utf-8")
    if args.out:
        _write_bytes(args.out, payload)
        _print_json({
            "out": args.out,
            "source_ref": source_ref,
            "unit_count": frame.unit_count,
            "block_count": frame.block_count,
            "separator_count": frame.separator_count,
        })
    else:
        sys.stdout.write(payload.decode("utf-8") + "\n")
    return tool_unit.EXIT_OK


def _load_proposals_file(path: str) -> dict:
    try:
        value = json.loads(_read_bytes(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticError(f"proposals file {path} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SemanticError(f"proposals file {path} must contain a JSON object")
    if value.get("schema_version") != PROPOSALS_SCHEMA_VERSION:
        raise SemanticError(
            f"proposals file {path}: schema_version must be "
            f"{PROPOSALS_SCHEMA_VERSION!r}, got {value.get('schema_version')!r}"
        )
    return value


def merge_proposals(documents: Sequence[dict]) -> dict:
    """Merge claim-proposals/1 documents in CLI order.

    ``assignments``/``decomposition``/``groups``/``precedence`` concatenate;
    duplicate ownership and duplicate ids still fail later in assembly /
    validation.  ``uncaptured_source_refs`` concatenates with first-seen
    de-duplication (the field is a set of source refs).
    """
    merged = {
        "schema_version": PROPOSALS_SCHEMA_VERSION,
        "assignments": [],
        "decomposition": [],
        "groups": [],
        "precedence": [],
        "uncaptured_source_refs": [],
    }
    for value in documents:
        for key in ("assignments", "decomposition", "groups", "precedence"):
            items = value.get(key) or []
            if not isinstance(items, list):
                raise SemanticError(f"proposals.{key} must be a list")
            merged[key].extend(items)
        refs = value.get("uncaptured_source_refs") or []
        if not isinstance(refs, list):
            raise SemanticError("proposals.uncaptured_source_refs must be a list")
        for ref in refs:
            if ref not in merged["uncaptured_source_refs"]:
                merged["uncaptured_source_refs"].append(ref)
    return merged


def cmd_assemble(args: argparse.Namespace) -> int:
    from .frame import frame_source
    from .registry import assemble_registry

    captures = read_capture_dir(args.captures)
    frames = {cap.source_ref: frame_source(cap.data) for cap in captures}
    documents = [_load_proposals_file(path) for path in args.proposals]
    proposals = merge_proposals(documents)
    window = {
        "version": "1",
        "max_units": args.window_max_units,
        "max_bytes": args.window_max_bytes,
        "overlap_units": args.window_overlap_units,
    }
    result = assemble_registry(captures, frames, proposals, window_recipe=window)
    _write_bytes(args.out, result.canonical_bytes)
    summary = {
        "out": args.out,
        "registry_hash": result.envelope["registry_hash"],
        "recipe_hash": result.payload["recipe_hash"],
        "sources": len(captures),
        "units": len(result.payload["units"]),
        "claims": len(result.payload["claims"]),
        "witness_complete": result.payload["witness"]["complete"],
        "notes": result.notes,
    }
    _print_json(summary)
    return tool_unit.EXIT_OK


def _load_windows(path: str | None) -> list[dict] | None:
    if not path:
        return None
    parsed = json.loads(_read_bytes(path).decode("utf-8"))
    if isinstance(parsed, dict) and "manifests" in parsed:
        return list(parsed["manifests"])
    return [parsed]


def cmd_validate(args: argparse.Namespace) -> int:
    from .validator import validate_registry

    raw = _read_bytes(args.registry)
    try:
        canonical.assert_canonical_bytes(raw)
    except canonical.CanonicalizationError as exc:
        report = {
            "valid": False,
            "errors": [f"canonical_bytes: {exc}"],
            "permission": {"complete_registry_claims": False, "finalized_unclaimed": False},
        }
        output = json.dumps(report, indent=2, ensure_ascii=False)
        if args.report_out:
            _write_bytes(args.report_out, output.encode("utf-8"))
        sys.stdout.write(output + "\n")
        return tool_unit.EXIT_FAIL
    envelope = canonical.canonical_loads(raw)
    captures = {cap.source_ref: cap.data for cap in read_capture_dir(args.captures)}
    report = validate_registry(
        envelope, captures, windows_manifests=_load_windows(args.windows), raw_bytes=raw
    )
    output = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    if args.report_out:
        _write_bytes(args.report_out, output.encode("utf-8"))
    sys.stdout.write(output + "\n")
    return tool_unit.EXIT_OK if report.valid else tool_unit.EXIT_FAIL


def cmd_frame_slices(args: argparse.Namespace) -> int:
    from claim_label_contract import slicing

    from .slices import frame_slices

    recipe = slicing.slice_recipe(
        max_bytes=args.max_bytes,
        max_units=args.max_units,
        max_input_bytes=args.max_input_bytes,
        overlap_units=args.overlap_units,
        max_slices=args.max_slices,
    )
    summary = frame_slices(args.captures, args.out_dir, recipe=recipe)
    _print_json(summary)
    return tool_unit.EXIT_OK


def cmd_proposal_reconcile(args: argparse.Namespace) -> int:
    from .proposal_reconcile import reconcile_run

    # A failed attempt must never leave a stale successful merge behind.
    if os.path.exists(args.out):
        try:
            os.remove(args.out)
        except OSError as exc:
            raise tool_unit.UsageError(
                f"proposal-reconcile: cannot remove existing --out {args.out!r}: {exc}"
            ) from exc
    merged, report = reconcile_run(args.captures, args.slices, args.proposal)
    if merged is not None:
        _write_bytes(args.out, merged)
    _write_bytes(args.report_out, canonical.canonical_dumps(report))
    _print_json({
        "out": args.out if merged is not None else None,
        "report": args.report_out,
        "complete": report["complete"],
        "merged_sha256": report["merged_sha256"],
        "conflicts": len(report["conflicts"]),
        "warnings": len(report["warnings"]),
    })
    return tool_unit.EXIT_OK if merged is not None else tool_unit.EXIT_FAIL


def cmd_windows(args: argparse.Namespace) -> int:
    from .frame import Unit
    from .registry import DEFAULT_WINDOW_RECIPE
    from .windows import build_windows, window_recipe

    payload = json.loads(_read_bytes(args.registry).decode("utf-8"))
    if not isinstance(payload, dict):
        raise SemanticError(f"registry {args.registry} must be a JSON object")
    if "payload" in payload:
        payload = payload["payload"]
    if not isinstance(payload, dict):
        raise SemanticError(f"registry {args.registry} payload must be a JSON object")
    recipe = payload.get("recipe", {}).get("window", DEFAULT_WINDOW_RECIPE)
    max_units = args.max_units if args.max_units is not None else recipe.get("max_units")
    max_bytes = args.max_bytes if args.max_bytes is not None else recipe.get("max_bytes")
    overlap = args.overlap_units if args.overlap_units is not None else recipe.get("overlap_units")
    window_recipe(max_units, max_bytes, overlap)  # fail loud on bad bounds

    units_by_source: dict[str, list] = {}
    for u in payload.get("units", []):
        unit = Unit(
            ordinal=u["ordinal"],
            kind=u["kind"],
            start=u["start"],
            end=u["end"],
            sha256=u["sha256"],
            ancestor_refs=tuple(u.get("ancestor_refs", [])),
        )
        units_by_source.setdefault(u["source_ref"], []).append(unit)
    manifests = []
    for ref in sorted(units_by_source):
        manifests.append(build_windows(ref, units_by_source[ref], max_units, max_bytes, overlap))
    out = {"schema_version": "window-manifests/1", "manifests": manifests}
    data = canonical.canonical_dumps(out)
    if args.out:
        _write_bytes(args.out, data)
        _print_json({
            "out": args.out,
            "manifests": len(manifests),
            "windows": sum(len(m["windows"]) for m in manifests),
        })
    else:
        sys.stdout.write(data.decode("utf-8") + "\n")
    return tool_unit.EXIT_OK


def cmd_hash(args: argparse.Namespace) -> int:
    raw = _read_bytes(args.input)
    result = {"input_sha256": canonical.hash_bytes(raw)}
    try:
        value = canonical.canonical_loads(raw)
    except canonical.CanonicalizationError as exc:
        result["canonical_error"] = str(exc)
        _print_json(result)
        return tool_unit.EXIT_FAIL
    try:
        result["canonical_sha256"] = canonical.hash_bytes(canonical.canonical_dumps(value))
    except canonical.CanonicalizationError as exc:
        result["canonical_error"] = str(exc)
        _print_json(result)
        return tool_unit.EXIT_FAIL
    if isinstance(value, dict) and isinstance(value.get("payload"), dict):
        payload = value["payload"]
        recomputed = canonical.registry_hash(payload)
        result["registry_hash"] = value.get("registry_hash")
        result["registry_hash_recomputed"] = recomputed
        result["registry_hash_matches"] = value.get("registry_hash") == recomputed
        if isinstance(payload.get("recipe"), dict):
            reci = canonical.recipe_hash(payload["recipe"])
            result["recipe_hash"] = payload.get("recipe_hash")
            result["recipe_hash_recomputed"] = reci
            result["recipe_hash_matches"] = payload.get("recipe_hash") == reci
    _print_json(result)
    return tool_unit.EXIT_OK


def _tool_block(args: argparse.Namespace) -> dict:
    """Tool identity + artifact pin for the run manifest.

    ``--tool-manifest`` (TOOL.json) wins; otherwise the running .pyz hashes
    itself; otherwise the artifact is null.
    """
    if args.tool_manifest:
        tool_json = json.loads(_read_bytes(args.tool_manifest).decode("utf-8"))
        if not isinstance(tool_json, dict):
            raise SemanticError(
                f"tool manifest {args.tool_manifest} must contain a JSON object"
            )
        describe_value = dict(tool_json)
        artifact = describe_value.get("artifact")
        describe_value["artifact"] = None
        if isinstance(artifact, dict):
            artifact = {
                "file": artifact.get("file"),
                "sha256": artifact.get("sha256"),
            }
        else:
            artifact = None
        return {
            "name": tool_json.get("name"),
            "version": tool_json.get("version"),
            "describe_sha256": tool_unit.sha256_bytes(
                tool_unit.describe_bytes(describe_value)
            ),
            "artifact": artifact,
        }
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0.endswith(".pyz") and os.path.isfile(argv0):
        artifact = {"file": os.path.basename(argv0), "sha256": tool_unit.sha256_file(argv0)}
    else:
        artifact = None
    return {
        "name": MANIFEST["name"],
        "version": MANIFEST["version"],
        "describe_sha256": tool_unit.describe_sha256(MANIFEST),
        "artifact": artifact,
    }


def cmd_manifest(args: argparse.Namespace) -> int:
    captures = read_capture_dir(args.captures)  # verifies raw files vs manifest
    manifest_path = os.path.join(args.captures, "manifest.json")
    captures_block = {
        "path": args.captures,
        "manifest_sha256": tool_unit.sha256_file(manifest_path),
    }

    proposals_block = []
    for path in args.proposals or []:
        proposals_block.append({"path": path, "sha256": tool_unit.sha256_file(path)})

    registry_block = None
    if args.registry:
        raw = _read_bytes(args.registry)
        canonical.assert_canonical_bytes(raw)
        envelope = canonical.canonical_loads(raw)
        if not isinstance(envelope, dict):
            raise SemanticError(
                f"registry {args.registry} must be a JSON object envelope"
            )
        registry_block = {
            "path": args.registry,
            "sha256": tool_unit.sha256_bytes(raw),
            "registry_hash": envelope.get("registry_hash"),
        }

    report_block = None
    if args.report:
        raw = _read_bytes(args.report)
        report = json.loads(raw.decode("utf-8"))
        if not isinstance(report, dict):
            raise SemanticError(f"report {args.report} must contain a JSON object")
        permission = report.get("permission")
        if not isinstance(permission, dict):
            permission = {}
        report_block = {
            "path": args.report,
            "sha256": tool_unit.sha256_bytes(raw),
            "valid": bool(report.get("valid")),
            "finalized_unclaimed": bool(permission.get("finalized_unclaimed")),
            "complete_registry_claims": bool(permission.get("complete_registry_claims")),
            "registry_hash": report.get("registry_hash"),
        }

    windows_block = None
    if args.windows:
        windows_block = {
            "path": args.windows,
            "sha256": tool_unit.sha256_file(args.windows),
        }

    value = {
        "schema_version": RUN_MANIFEST_SCHEMA,
        "tool": _tool_block(args),
        "captures": captures_block,
        "proposals": proposals_block,
        "registry": registry_block,
        "report": report_block,
        "windows": windows_block,
    }
    tool_unit.json_write(args.out, value)
    _print_json({
        "out": args.out,
        "schema_version": RUN_MANIFEST_SCHEMA,
        "tool": {
            "name": value["tool"]["name"],
            "version": value["tool"]["version"],
        },
        "sources": len(captures),
        "proposals": len(proposals_block),
    })
    return tool_unit.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claim_registry.cli",
                                     description="Minimal claim-registry pilot producer.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("capture", help="capture source bytes verbatim + identity")
    p.add_argument("--in", dest="input", required=True, action="append",
                   help="source file captured verbatim; repeatable (one per source)")
    p.add_argument("--locator", required=True, action="append",
                   help="authority locator paired with --in by position; repeatable")
    p.add_argument("--class", dest="source_class", action="append", default=None,
                   help="source class; pass once (all sources) or once per source")
    p.add_argument("--pointer-ref", action="append", default=None,
                   help="optional pointer ref; pass once (all sources) or once per source")
    p.add_argument("--interpretation-ref", action="append", default=None,
                   help="optional interpretation ref; once (all sources) or once per source")
    p.add_argument("--out", required=True,
                   help="capture directory (one manifest; never overwritten)")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("frame", help="extract the atomic-unit frame")
    p.add_argument("--in", dest="input", required=True)
    p.add_argument("--locator", default=None,
                   help="authority locator; computes source_ref from captured bytes")
    p.add_argument("--source-ref", default=None,
                   help="explicit source_ref (overrides --locator)")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_frame)

    p = sub.add_parser("assemble", help="assemble canonical registry from captures+proposals")
    p.add_argument("--captures", required=True, help="capture directory")
    p.add_argument("--proposals", required=True, action="append",
                   help="claim-proposals/1 file; repeatable, merged in CLI order")
    p.add_argument("--out", required=True)
    p.add_argument("--window-max-units", type=int, default=WINDOW_MAX_UNITS)
    p.add_argument("--window-max-bytes", type=int, default=WINDOW_MAX_BYTES)
    p.add_argument("--window-overlap-units", type=int, default=WINDOW_OVERLAP_UNITS)
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("frame-slices", help="bounded byte-exact worker payloads")
    p.add_argument("--captures", required=True, help="capture directory from capture")
    p.add_argument("--out-dir", required=True,
                   help="fresh manifest directory (never overwritten)")
    p.add_argument("--max-bytes", type=int, default=FRAME_SLICE_MAX_BYTES,
                   help="max raw text bytes per slice")
    p.add_argument("--max-units", type=int, default=FRAME_SLICE_MAX_UNITS,
                   help="max units per slice (separators included)")
    p.add_argument("--max-input-bytes", type=int, default=FRAME_SLICE_MAX_INPUT_BYTES,
                   help="max serialized worker input bytes per slice")
    p.add_argument("--overlap-units", type=int, default=FRAME_SLICE_OVERLAP_UNITS,
                   help="target preceding audit units")
    p.add_argument("--max-slices", type=int, default=FRAME_SLICE_MAX_SLICES,
                   help="run slice budget; exceeding it fails, never truncates")
    p.set_defaults(func=cmd_frame_slices)

    p = sub.add_parser("proposal-reconcile",
                       help="merge per-slice proposals deterministically")
    p.add_argument("--captures", required=True, help="capture directory from capture")
    p.add_argument("--slices", required=True, help="frame-slices/1 manifest.json")
    p.add_argument("--proposal", required=True, action="append",
                   help="slice-proposals/1 file; repeatable (one per slice)")
    p.add_argument("--out", required=True,
                   help="merged claim-proposals/1 output (removed on any failure)")
    p.add_argument("--report-out", required=True,
                   help="proposal-reconciliation/1 report (canonical bytes)")
    p.set_defaults(func=cmd_proposal_reconcile)

    p = sub.add_parser("validate", help="independent recompute/validation")
    p.add_argument("--registry", required=True)
    p.add_argument("--captures", required=True, help="capture directory")
    p.add_argument("--windows", default=None, help="optional window manifest JSON")
    p.add_argument("--report-out", default=None)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("windows", help="build bounded window manifests")
    p.add_argument("--registry", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--max-units", type=int, default=None)
    p.add_argument("--max-bytes", type=int, default=None)
    p.add_argument("--overlap-units", type=int, default=None)
    p.set_defaults(func=cmd_windows)

    p = sub.add_parser("hash", help="canonical hash of a JSON file / registry")
    p.add_argument("--in", dest="input", required=True)
    p.set_defaults(func=cmd_hash)

    p = sub.add_parser("manifest", help="seal a completed run into claim-run-manifest/1")
    p.add_argument("--captures", required=True, help="capture directory")
    p.add_argument("--proposals", action="append", default=None,
                   help="claim-proposals/1 file; repeatable, recorded in CLI order")
    p.add_argument("--registry", default=None, help="registry envelope")
    p.add_argument("--report", default=None, help="validation report")
    p.add_argument("--windows", default=None, help="optional window manifests")
    p.add_argument("--tool-manifest", dest="tool_manifest", default=None,
                   help="TOOL.json artifact pin; default: self-hash when running from a .pyz")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_manifest)
    return parser


def _dependency_failure(message: str) -> int:
    sys.stderr.write(f"error: {message}\n")
    sys.stderr.write(
        f"install: {tool_unit.install_hint(MANIFEST['dependencies'])}\n"
    )
    return tool_unit.EXIT_USAGE


def _check_dependencies() -> int | None:
    try:
        tool_unit.require_dependencies(MANIFEST["dependencies"])
    except tool_unit.DependencyError as exc:
        return _dependency_failure(str(exc))
    # Metadata can claim the pinned version while the import path is broken
    # (shadowed package, missing/broken C extension): fail loud with the hint.
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_markdown  # noqa: F401
    except ImportError as exc:
        return _dependency_failure(f"pinned dependency import failed: {exc}")
    return None


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    code = tool_unit.run_describe(MANIFEST, args_list)
    if code is not None:
        return code
    parser = build_parser()
    args = parser.parse_args(args_list)
    failure = _check_dependencies()
    if failure is not None:
        return failure
    # Pinned dependencies are importable past this point; the heavy frame
    # walker is imported here only (never at module import / --describe time).
    from claim_label_contract.reconciliation import ReconciliationReportError
    from claim_label_contract.slicing import SlicePlanError, SliceRecipeError
    from .frame import ExtractionError
    from .registry import RegistryAssemblyError
    from .windows import WindowRecipeError

    try:
        return args.func(args)
    except (
        ExtractionError,
        ReconciliationReportError,
        RegistryAssemblyError,
        SemanticError,
        SlicePlanError,
        canonical.CanonicalizationError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return tool_unit.EXIT_FAIL
    except (tool_unit.UsageError, WindowRecipeError, SliceRecipeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return tool_unit.EXIT_USAGE
    except OSError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return tool_unit.EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
