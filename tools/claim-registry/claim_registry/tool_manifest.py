"""Static ``tool-unit/1`` manifest for the claim-registry producer unit.

Importable **without** tree-sitter: nothing in this module imports the frame
walker, and the shared ``toolkit`` import falls back to the sibling ``common/``
directory when the unit runs from a development checkout (the packaged ``.pyz``
bundles ``toolkit/`` at its archive root).  ``--describe`` therefore works
before any dependency is installed.

The runtime recipe pins below are literals; ``tests/test_tool_unit.py`` checks
them against the live ``frame_recipe()`` / ``DEFAULT_WINDOW_RECIPE`` so they
cannot drift silently.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:  # packaged .pyz: toolkit/ is bundled at the archive root
    from toolkit import tool_unit
except ModuleNotFoundError:  # dev checkout: ../common is not on sys.path yet
    _COMMON = Path(__file__).resolve().parents[2] / "common"
    if str(_COMMON) not in sys.path:
        sys.path.insert(0, str(_COMMON))
    from toolkit import tool_unit

NAME = "claim-registry"
VERSION = "0.3.0"
SUMMARY = (
    "Deterministic pilot producer for cure-light claim registries: verbatim "
    "capture, strict atomic-unit Markdown frame, claim-json/1 canonical "
    "assembly, independent validation, bounded windows, run manifest."
)

#: The window recipe default mirrored from claim_registry.registry (literals so
#: that the parser and the manifest never import the tree-sitter walker).
WINDOW_MAX_UNITS = 64
WINDOW_MAX_BYTES = 65536
WINDOW_OVERLAP_UNITS = 8

#: Slice recipe defaults mirrored from claim_label_contract.slicing.
FRAME_SLICE_MAX_BYTES = 16384
FRAME_SLICE_MAX_UNITS = 80
FRAME_SLICE_MAX_INPUT_BYTES = 65536
FRAME_SLICE_OVERLAP_UNITS = 4
FRAME_SLICE_MAX_SLICES = 32


def _dependency(name: str, version: str) -> dict:
    dep = {
        "name": name,
        "verified_version": version,
        "spec": f"=={version}",
    }
    dep["install"] = tool_unit.install_hint([dep])
    return dep


DEPENDENCIES = [
    _dependency("tree-sitter", "0.26.0"),
    _dependency("tree-sitter-markdown", "0.5.1"),
]


def _param(name, type_, required, default, description) -> dict:
    return {
        "name": name,
        "type": type_,
        "required": required,
        "default": default,
        "description": description,
    }


_EXIT_DESCRIBE = {
    "0": "describe/check-pin handled before argument parsing; no dependencies needed",
    "2": "--check-pin without exactly one sha256, or not running from a .pyz artifact",
}

COMMANDS = {
    "capture": {
        "usage": (
            "claim-registry capture --in SOURCE --locator LOCATOR "
            "[--in SOURCE --locator LOCATOR ...] "
            "[--class CLASS] [--pointer-ref REF] [--interpretation-ref REF] --out DIR"
        ),
        "summary": (
            "Capture one or more source files verbatim and write a single "
            "capture-manifest/1 directory (raw sha256, byte length, synthetic "
            "git blob OID, source_ref); records follow CLI order."
        ),
        "params": [
            _param("--in", "path", True, None, "source file captured verbatim (no normalization); repeatable"),
            _param("--locator", "string", True, None, "authority locator, e.g. 'repo#17:body'; repeatable, paired with --in by position"),
            _param("--class", "string", False, "api-document", "source class; once (all sources) or once per source"),
            _param("--pointer-ref", "string", False, None, "optional pointer/reference; once or once per source"),
            _param("--interpretation-ref", "string", False, None, "optional interpretation reference; once or once per source"),
            _param("--out", "path", True, None, "capture directory to create (manifest.json + raw/); never overwritten"),
        ],
        "outputs": {
            "stdout": "JSON summary {manifest, source} (single) or {manifest, sources} (batch)",
            "<out>/manifest.json": "capture-manifest/1 canonical JSON",
            "<out>/raw/*.bin": "verbatim source bytes in CLI order",
        },
        "exit_codes": {
            "0": "capture directory written",
            "1": "not produced by capture",
            "2": "bad --in/--locator/metadata pairing, duplicate locator, existing manifest, missing/unreadable --in, unwritable --out",
        },
    },
    "frame": {
        "usage": (
            "claim-registry frame --in SOURCE (--locator LOCATOR | --source-ref REF) "
            "[--out FRAME.json]"
        ),
        "summary": (
            "Extract the deterministic atomic-unit frame (strict byte partition, "
            "pinned walker/parser recipe)."
        ),
        "params": [
            _param("--in", "path", True, None, "source file to frame"),
            _param("--locator", "string", False, None, "authority locator; computes source_ref from the bytes"),
            _param("--source-ref", "string", False, None, "explicit source_ref (overrides --locator)"),
            _param("--out", "path", False, None, "write the frame JSON here instead of stdout"),
        ],
        "outputs": {
            "stdout": "frame JSON {source_ref, unit_count, block_count, separator_count, recipe, units}",
            "<out>": "same frame JSON written to a file",
        },
        "exit_codes": {
            "0": "frame emitted",
            "1": "ExtractionError: parse error or non-whitespace gap (message carries byte offset + snippet)",
            "2": "missing --in file, or neither --locator nor --source-ref given",
        },
    },
    "assemble": {
        "usage": (
            "claim-registry assemble --captures DIR --proposals P.json "
            "[--proposals P2.json ...] --out REGISTRY.json "
            "[--window-max-units N] [--window-max-bytes N] [--window-overlap-units N]"
        ),
        "summary": (
            "Assemble the canonical claim-json/1 registry envelope from captures "
            "and one or more agent-authored claim-proposals/1 files (merged in CLI order)."
        ),
        "params": [
            _param("--captures", "path", True, None, "capture directory from capture"),
            _param("--proposals", "path", True, None, "claim-proposals/1 file; repeatable, merged in CLI order"),
            _param("--out", "path", True, None, "registry envelope output (canonical, no trailing newline)"),
            _param("--window-max-units", "int", False, WINDOW_MAX_UNITS, "window recipe max units"),
            _param("--window-max-bytes", "int", False, WINDOW_MAX_BYTES, "window recipe max bytes"),
            _param("--window-overlap-units", "int", False, WINDOW_OVERLAP_UNITS, "window recipe overlap units"),
        ],
        "outputs": {
            "stdout": "JSON summary {out, registry_hash, recipe_hash, sources, units, claims, witness_complete, notes}",
            "<out>": "claim-registry/1 canonical envelope {payload, registry_hash}",
        },
        "exit_codes": {
            "0": "canonical registry written",
            "1": "RegistryAssemblyError: malformed proposals JSON, unknown/double-owned unit_id, non-consecutive claim, unowned decomposition remainder",
            "2": "missing --captures/--proposals files or invalid window bounds (WindowRecipeError)",
        },
    },
    "validate": {
        "usage": (
            "claim-registry validate --registry REGISTRY.json --captures DIR "
            "[--windows W.json] [--report-out REPORT.json]"
        ),
        "summary": (
            "Independently recompute the registry against the captures: hashes, "
            "re-extracted units, ownership, witness, windows, permissions."
        ),
        "params": [
            _param("--registry", "path", True, None, "registry envelope from assemble"),
            _param("--captures", "path", True, None, "capture directory from capture"),
            _param("--windows", "path", False, None, "optional window manifests from windows"),
            _param("--report-out", "path", False, None, "also write the validation report here"),
        ],
        "outputs": {
            "stdout": "validation report JSON {valid, registry_hash, checks[], errors[], recomputed_witness, permission}",
            "<report-out>": "same report JSON written to a file",
        },
        "exit_codes": {
            "0": "valid == true; permission.finalized_unclaimed and permission.complete_registry_claims are true",
            "1": "invalid: report.errors names the exact unit_id/field/check; also non-canonical registry bytes or malformed JSON",
            "2": "missing registry/captures files or unreadable capture directory",
        },
    },
    "windows": {
        "usage": (
            "claim-registry windows --registry REGISTRY.json [--out W.json] "
            "[--max-units N] [--max-bytes N] [--overlap-units N]"
        ),
        "summary": "Build bounded, reconcilable ingestion window manifests from registry units.",
        "params": [
            _param("--registry", "path", True, None, "registry envelope from assemble"),
            _param("--out", "path", False, None, "write window-manifests/1 here instead of stdout"),
            _param("--max-units", "int", False, None, "override max units (default: registry window recipe)"),
            _param("--max-bytes", "int", False, None, "override max bytes (default: registry window recipe)"),
            _param("--overlap-units", "int", False, None, "override overlap units (default: registry window recipe)"),
        ],
        "outputs": {
            "stdout": "window-manifests/1 canonical JSON",
            "<out>": "same window manifests written to a file",
        },
        "exit_codes": {
            "0": "window manifests written",
            "1": "registry is malformed JSON",
            "2": "missing registry file or invalid window bounds (WindowRecipeError / OversizedUnitError)",
        },
    },
    "frame-slices": {
        "usage": (
            "claim-registry frame-slices --captures DIR --out-dir DIR "
            "[--max-bytes N] [--max-units N] [--max-input-bytes N] "
            "[--overlap-units N] [--max-slices N]"
        ),
        "summary": (
            "Frame every captured source exactly once and write bounded "
            "byte-exact frame-slice-input/1 worker payloads plus the closed "
            "frame-slices/1 manifest; cores partition each source once and at "
            "most --overlap-units preceding units are audit-only overlap."
        ),
        "params": [
            _param("--captures", "path", True, None, "capture directory from capture"),
            _param("--out-dir", "path", True, None, "fresh manifest directory (never overwritten)"),
            _param("--max-bytes", "int", False, FRAME_SLICE_MAX_BYTES, "max raw text bytes per slice"),
            _param("--max-units", "int", False, FRAME_SLICE_MAX_UNITS, "max units per slice (separators included)"),
            _param("--max-input-bytes", "int", False, FRAME_SLICE_MAX_INPUT_BYTES, "max serialized worker input bytes per slice"),
            _param("--overlap-units", "int", False, FRAME_SLICE_OVERLAP_UNITS, "target preceding audit units"),
            _param("--max-slices", "int", False, FRAME_SLICE_MAX_SLICES, "run slice budget; exceeding it fails, never truncates"),
        ],
        "outputs": {
            "stdout": "JSON summary {out_dir, manifest, sources, slices, captures_sha256, slice_recipe_hash}",
            "<out-dir>/manifest.json": "frame-slices/1 canonical JSON",
            "<out-dir>/payload/*.json": "frame-slice-input/1 canonical payloads",
        },
        "exit_codes": {
            "0": "manifest directory written",
            "1": "named slicing failure: oversized unit, unverified zero-overlap seam, byte/payload budget, invalid UTF-8, capture verification, max_slices breach",
            "2": "bad caps/arguments, existing --out-dir, missing capture files, missing pinned dependency",
        },
    },
    "proposal-reconcile": {
        "usage": (
            "claim-registry proposal-reconcile --captures DIR --slices MANIFEST.json "
            "[--proposal P.json ...] --out MERGED.json --report-out REPORT.json"
        ),
        "summary": (
            "Replay the frame-slices/1 manifest against the captures, admit one "
            "slice-proposals/1 per slice, reconcile ownership/overlap/grouping/"
            "boundaries deterministically and write one claim-proposals/1 plus "
            "a proposal-reconciliation/1 report; any conflict exits 1 with a "
            "failure report and no merged artifact."
        ),
        "params": [
            _param("--captures", "path", True, None, "capture directory from capture"),
            _param("--slices", "path", True, None, "frame-slices/1 manifest.json"),
            _param("--proposal", "path", False, None, "slice-proposals/1 file; repeatable (one per slice; none is valid only for zero-slice manifests)"),
            _param("--out", "path", True, None, "merged claim-proposals/1 output (removed on any failure)"),
            _param("--report-out", "path", True, None, "proposal-reconciliation/1 report (canonical bytes)"),
        ],
        "outputs": {
            "stdout": "JSON summary {out, report, complete, merged_sha256, conflicts, warnings}",
            "<out>": "claim-proposals/1 canonical merged document (success only)",
            "<report-out>": "proposal-reconciliation/1 canonical report",
        },
        "exit_codes": {
            "0": "every slice reconciled; merged + complete report written",
            "1": "named conflict(s); failure report written (merged_sha256 null) and no merged artifact",
            "2": "bad arguments or missing/unreadable captures, manifest or proposal files",
        },
    },
    "hash": {
        "usage": "claim-registry hash --in FILE",
        "summary": (
            "Compute raw sha256 plus canonical claim-json/1 hashes "
            "(registry_hash/recipe_hash when the input is a registry envelope)."
        ),
        "params": [
            _param("--in", "path", True, None, "JSON file to hash"),
        ],
        "outputs": {
            "stdout": "JSON {input_sha256, canonical_sha256, registry_hash*, recipe_hash*}",
        },
        "exit_codes": {
            "0": "hashes computed",
            "1": "input is not canonical claim-json/1 (canonical_error reported)",
            "2": "missing/unreadable input file",
        },
    },
    "manifest": {
        "usage": (
            "claim-registry manifest --captures DIR [--proposals P.json ...] "
            "[--registry R.json] [--report V.json] [--windows W.json] "
            "[--tool-manifest TOOL.json] --out MANIFEST.json | "
            "claim-registry manifest --captures DIR --slices S.json "
            "--slice-proposal C.json ... --reconciliation R.json "
            "--proposals MERGED.json [...] --out MANIFEST.json"
        ),
        "summary": (
            "Seal a completed run into a canonical claim-run-manifest/1 (legacy) "
            "or /2 when --slices/--slice-proposal/--reconciliation are given: tool "
            "identity/pin, input paths + sha256, registry/report key fields and the "
            "mandatory sliced labeling block (slices manifest, every child "
            "proposal, merged proposals, reconciliation report)."
        ),
        "params": [
            _param("--captures", "path", True, None, "capture directory from capture"),
            _param("--proposals", "path", False, None, "claim-proposals/1 file; repeatable (sliced mode: exactly one merged file)"),
            _param("--slices", "path", False, None, "frame-slices/1 manifest.json (claim-run-manifest/2)"),
            _param("--slice-proposal", "path", False, None, "slice-proposals/1 child file; repeatable, one per slice"),
            _param("--reconciliation", "path", False, None, "proposal-reconciliation/1 report (claim-run-manifest/2)"),
            _param("--registry", "path", False, None, "registry envelope from assemble"),
            _param("--report", "path", False, None, "validation report from validate"),
            _param("--windows", "path", False, None, "optional window manifests from windows"),
            _param("--tool-manifest", "path", False, None, "TOOL.json of the tool unit (artifact pin); else self-hash when running from a .pyz"),
            _param("--out", "path", True, None, "claim-run-manifest/1|2 output (canonical, no trailing newline)"),
        ],
        "outputs": {
            "stdout": "JSON summary {out, schema_version, tool}",
            "<out>": "claim-run-manifest/1 or claim-run-manifest/2 canonical JSON",
        },
        "exit_codes": {
            "0": "run manifest written",
            "1": "malformed/non-canonical sliced evidence, incomplete reconciliation, or capture verification failure",
            "2": "missing/unreadable input file, capture directory, or incomplete new-flag combination",
        },
    },
}


RECIPE_PINS = {
    "frame_recipe": "claim-registry-frame/1",
    "parser": "tree-sitter-markdown 0.5.1",
    "runtime": "tree-sitter 0.26.0",
    "canonicalization": "claim-json/1",
    "run_manifest_schema": "claim-run-manifest/2 (sliced) / claim-run-manifest/1 (legacy)",
    "window_recipe": (
        "claim-registry-window/1 max_units=64 max_bytes=65536 overlap_units=8"
    ),
    "slice_recipe": (
        "claim-registry-slice/1 greedy-largest-core/1 max_bytes=16384 "
        "max_units=80 max_input_bytes=65536 overlap_units=4 max_slices=32"
    ),
}

DETERMINISM = {
    "idempotent": True,
    "no_hidden_state": True,
    "identical_inputs_to_identical_outputs": True,
    "notes": (
        "pure file/JSON in -> file/JSON out; canonical claim-json/1 bytes with no "
        "trailing newline; no timestamps; frame walker/parser/runtime versions and "
        "the walker script sha256 are pinned in the registry recipe; proposals are "
        "the only agent-authored input"
    ),
}

MANIFEST = tool_unit.build_manifest(
    name=NAME,
    version=VERSION,
    summary=SUMMARY,
    dependencies=DEPENDENCIES,
    commands=COMMANDS,
    requires_python=">=3.11",
    recipe_pins=RECIPE_PINS,
    determinism=DETERMINISM,
)

__all__ = [
    "COMMANDS",
    "DEPENDENCIES",
    "DETERMINISM",
    "FRAME_SLICE_MAX_BYTES",
    "FRAME_SLICE_MAX_INPUT_BYTES",
    "FRAME_SLICE_MAX_SLICES",
    "FRAME_SLICE_MAX_UNITS",
    "FRAME_SLICE_OVERLAP_UNITS",
    "MANIFEST",
    "NAME",
    "RECIPE_PINS",
    "SUMMARY",
    "VERSION",
    "WINDOW_MAX_BYTES",
    "WINDOW_MAX_UNITS",
    "WINDOW_OVERLAP_UNITS",
]
