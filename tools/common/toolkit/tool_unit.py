"""Tool-unit contract helpers shared by every cure-light agentic tool unit.

A tool unit is one fetchable artifact (``<name>-<version>.pyz``) plus a
``TOOL.json`` manifest.  See ``tools/DESIGN.md`` section 1 for the contract.

This module is stdlib-only and must stay importable without the unit's heavy
dependencies (``--describe`` has to work before anything is installed).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import canonical_json

TOOL_UNIT_SCHEMA = "tool-unit/1"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

EXIT_CODE_MEANING = {
    "0": "ok",
    "1": (
        "semantic or validation failure; read report.errors (each names the "
        "exact unit_id/field/check)"
    ),
    "2": "usage or environment failure (bad arguments, missing/wrong pinned dependency)",
}


class UsageError(Exception):
    """Bad invocation or missing/unreadable input file -> exit 2."""


class DependencyError(Exception):
    """A pinned dependency is missing or wrong -> exit 2 with an install hint."""

    def __init__(self, packages: Sequence[Mapping[str, Any]]) -> None:
        self.packages = list(packages)
        detail = ", ".join(
            f"{p['name']}=={p.get('verified_version', p.get('spec', '?'))}"
            + (f" (found {p['found']})" if p.get("found") else " (not installed)")
            for p in packages
        )
        super().__init__(f"missing or mismatched pinned dependencies: {detail}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    *,
    name: str,
    version: str,
    summary: str,
    dependencies: Sequence[Mapping[str, Any]],
    commands: Mapping[str, Mapping[str, Any]],
    requires_python: str = ">=3.11",
    recipe_pins: Mapping[str, str] | None = None,
    determinism: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict:
    """Assemble a ``tool-unit/1`` manifest with a stable field order."""
    manifest: dict[str, Any] = {
        "schema_version": TOOL_UNIT_SCHEMA,
        "name": name,
        "version": version,
        "summary": summary,
        "requires_python": requires_python,
        "dependencies": [dict(dep) for dep in dependencies],
        "commands": {key: dict(value) for key, value in commands.items()},
        "exit_codes": dict(EXIT_CODE_MEANING),
        "determinism": dict(
            determinism
            or {
                "idempotent": True,
                "no_hidden_state": True,
                "identical_inputs_to_identical_outputs": True,
                "notes": "pure file/JSON in -> file/JSON out",
            }
        ),
        "recipe_pins": dict(recipe_pins or {}),
        "artifact": None,
        "artifact_note": (
            "TOOL.json carries artifact.sha256; every other field must match "
            "--describe exactly"
        ),
    }
    if extra:
        manifest.update(extra)
    return manifest


def describe_bytes(manifest: Mapping[str, Any]) -> bytes:
    """Canonical ``--describe`` payload: no trailing newline, no environment data."""
    return canonical_json.canonical_dumps(dict(manifest))


def describe_sha256(manifest: Mapping[str, Any]) -> str:
    return sha256_bytes(describe_bytes(manifest))


def tool_json_bytes(
    manifest: Mapping[str, Any],
    *,
    artifact_file: str,
    artifact_sha256: str,
    artifact_size: int,
) -> bytes:
    """``TOOL.json`` bytes: describe payload plus the artifact pin block."""
    value = dict(manifest)
    value["artifact"] = {
        "file": artifact_file,
        "sha256": artifact_sha256,
        "size": artifact_size,
    }
    return canonical_json.canonical_dumps(value)


def install_hint(dependencies: Sequence[Mapping[str, Any]]) -> str:
    specs = " ".join(
        "'{}=={}'".format(dep["name"], dep.get("verified_version", dep.get("spec", "")))
        for dep in dependencies
    )
    return f"python3 -m pip install {specs}".strip()


def require_dependencies(dependencies: Sequence[Mapping[str, Any]]) -> None:
    """Fail loud unless every dependency is installed at the verified version.

    Exact-match policy: determinism depends on the pinned parser/runtime, and
    the frame recipe records the concrete versions.  Any other version is an
    error, not a warning.
    """
    bad: list[dict[str, Any]] = []
    for dep in dependencies:
        name = str(dep["name"])
        expected = str(dep.get("verified_version") or dep.get("spec"))
        try:
            found = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found = None
        if found != expected:
            bad.append({"name": name, "verified_version": expected, "found": found})
    if bad:
        raise DependencyError(bad)


def json_write(path: str | Path, value: Any) -> bytes:
    """Write canonical bytes (no trailing newline); returns the bytes."""
    data = canonical_json.canonical_dumps(value)
    path = Path(path)
    if path.parent and str(path.parent):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def json_read(path: str | Path) -> Any:
    """Strict canonical JSON reader (duplicate keys and bad types rejected)."""
    return canonical_json.canonical_loads(Path(path).read_bytes())


def emit_json(value: Any, *, trailing_newline: bool = True) -> None:
    data = canonical_json.canonical_dumps(value)
    sys.stdout.buffer.write(data)
    if trailing_newline:
        sys.stdout.buffer.write(b"\n")
    sys.stdout.flush()


def _artifact_path(argv0: str | None) -> Path | None:
    argv0 = argv0 if argv0 is not None else sys.argv[0]
    if not argv0 or not argv0.endswith(".pyz"):
        return None
    path = Path(argv0)
    if not path.is_file():
        return None
    return path


def run_describe(
    manifest: Mapping[str, Any],
    argv: Sequence[str] | None = None,
    *,
    argv0: str | None = None,
) -> int | None:
    """Handle the universal ``--describe`` / ``--check-pin`` flags.

    Returns an exit code when the flag was consumed, else ``None`` so the unit
    can continue into its own argument parsing.
    """
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        return None
    if args[0] == "--describe":
        emit_json(manifest)
        return EXIT_OK
    if args[0] == "--check-pin":
        if len(args) != 2:
            sys.stderr.write("error: --check-pin requires exactly one sha256\n")
            return EXIT_USAGE
        artifact = _artifact_path(argv0)
        if artifact is None:
            sys.stderr.write(
                "error: --check-pin must run from the packaged .pyz artifact "
                f"(argv[0]={sys.argv[0]!r}); use sha256sum on the downloaded file\n"
            )
            return EXIT_USAGE
        actual = sha256_file(artifact)
        expected = args[1].strip().lower()
        if actual == expected:
            sys.stderr.write(f"pin ok: {artifact} {actual}\n")
            return EXIT_OK
        sys.stderr.write(
            f"error: artifact pin mismatch: expected {expected}, got {actual} "
            f"for {artifact}\n"
        )
        return EXIT_FAIL
    return None
