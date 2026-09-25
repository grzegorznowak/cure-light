"""Build a real gate-check fixture from the read-only baseline producer.

Runs the baseline ``claim_registry.cli`` subcommands (capture/assemble/validate)
against the committed in-tree fixture
``tools/claim-registry/tests/fixtures/pr17-body-v2.md`` (sha256-pinned below so
drift fails loudly) inside a temp directory, and constructs the
``claim-run-manifest/1`` in-process with hashlib + the vendored canonical JSON.
Nothing is ever written into the baseline or any repo.

Used by the test-suite and for the manual built-artifact smoke run::

    python3 tests/fixture_builder.py /tmp/gate-check-fixture
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

UNIT = Path(__file__).resolve().parents[1]
COMMON = UNIT.parent / "common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))

from toolkit import canonical_json  # noqa: E402

SOURCE = UNIT.parent / "claim-registry" / "tests" / "fixtures" / "pr17-body-v2.md"
SOURCE_SHA256 = "10b5b3018d8928ce607735a6c31181be463f983bbc21ba07aa1985b9b4e1c2a7"
SOURCE_BYTE_LENGTH = 10385


class FixtureSourceError(RuntimeError):
    """Committed fixture source missing or drifted: hard failure, never skip."""


def find_baseline() -> Path | None:
    """The producer is always the sibling ``tools/claim-registry`` unit."""
    candidate = UNIT.parent / "claim-registry"
    if (candidate / "claim_registry" / "cli.py").is_file():
        return candidate
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source() -> Path:
    """Resolve the committed fixture source; missing/drifted -> hard failure."""
    if not SOURCE.is_file():
        raise FixtureSourceError(f"committed fixture source missing: {SOURCE}")
    actual_sha = sha256_file(SOURCE)
    actual_len = SOURCE.stat().st_size
    if actual_sha != SOURCE_SHA256 or actual_len != SOURCE_BYTE_LENGTH:
        raise FixtureSourceError(
            f"committed fixture source drift: {SOURCE} sha256 {actual_sha} "
            f"({actual_len} B) != pinned {SOURCE_SHA256} ({SOURCE_BYTE_LENGTH} B)"
        )
    return SOURCE


def _run_producer(baseline: Path, args: list[str], cwd: Path) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(baseline) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # baseline stays read-only, incl. .pyc
    proc = subprocess.run(
        [sys.executable, "-m", "claim_registry.cli", *args],
        cwd=str(cwd), env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"producer {' '.join(args)} failed rc={proc.returncode}: {proc.stderr[-2000:]}"
        )
    return proc.stdout


def build_proposals(frame: dict) -> dict:
    """Mirror the producer's default proposals: every unit owned, separators context."""
    assignments = []
    for unit in frame["units"]:
        if unit["kind"] == "separator":
            assignments.append({
                "source_ref": unit["source_ref"],
                "unit_ids": [unit["unit_id"]],
                "state": "nonclaim",
                "label": "context",
                "rationale": "mechanical separator",
                "role_ref": "spec:claim-registry/1#separator",
            })
        else:
            assignments.append({
                "source_ref": unit["source_ref"],
                "unit_ids": [unit["unit_id"]],
                "state": "claim",
                "rationale": "",
            })
    return {"schema_version": "claim-proposals/1", "assignments": assignments}


def build_fixture(dest: Path) -> dict:
    baseline = find_baseline()
    if baseline is None:
        raise RuntimeError("baseline producer not found")
    source = load_source()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    locator = source.name
    captures = dest / "captures"
    proposals = dest / "proposals.json"
    registry = dest / "registry.json"
    report = dest / "report.json"

    _run_producer(baseline, [
        "capture", "--in", str(source), "--locator", locator, "--out", str(captures),
    ], dest)
    frame = json.loads(_run_producer(baseline, [
        "frame", "--in", str(source), "--locator", locator,
    ], dest))
    proposals.write_text(json.dumps(build_proposals(frame), indent=2), encoding="utf-8")
    _run_producer(baseline, [
        "assemble", "--captures", str(captures), "--proposals", str(proposals),
        "--out", str(registry),
    ], dest)
    _run_producer(baseline, [
        "validate", "--registry", str(registry), "--captures", str(captures),
        "--report-out", str(report),
    ], dest)

    # The baseline ships no TOOL.json; build a synthetic, self-consistent pin so
    # the tool-pin checks can be exercised (the gate recomputes describe_sha256
    # from TOOL.json minus artifact).
    artifact = dest / "fake-claim-registry-artifact.bin"
    artifact.write_bytes(b"pinned claim-registry artifact fixture\n")
    tool_manifest: dict = {
        "schema_version": "tool-unit/1",
        "name": "claim-registry",
        "version": "0.1.0",
        "summary": "fixture stand-in for the producer TOOL.json",
        "dependencies": [],
        "commands": {},
    }
    tool_manifest["artifact"] = {
        "file": "dist/claim-registry-0.1.0.pyz",
        "sha256": sha256_file(artifact),
        "size": artifact.stat().st_size,
    }
    tool_manifest_path = dest / "TOOL.json"
    tool_manifest_path.write_bytes(canonical_json.canonical_dumps(tool_manifest))
    # Producer recipe: hash the describe payload with ``artifact`` normalized to
    # null (claim_registry.cli._tool_block), not with the key removed.
    describe_value = dict(tool_manifest)
    describe_value["artifact"] = None
    describe_sha = hashlib.sha256(
        canonical_json.canonical_dumps(describe_value)
    ).hexdigest()

    envelope = json.loads(registry.read_bytes())
    report_value = json.loads(report.read_bytes())
    permission = report_value.get("permission")
    permission = permission if isinstance(permission, dict) else {}
    manifest = {
        "schema_version": "claim-run-manifest/1",
        "tool": {
            "name": "claim-registry",
            "version": "0.1.0",
            "describe_sha256": describe_sha,
            "artifact": {
                "file": tool_manifest["artifact"]["file"],
                "sha256": tool_manifest["artifact"]["sha256"],
            },
        },
        "captures": {
            "path": "captures",
            "manifest_sha256": sha256_file(captures / "manifest.json"),
        },
        "proposals": [
            {"path": "proposals.json", "sha256": sha256_file(proposals)}
        ],
        "registry": {
            "path": "registry.json",
            "sha256": sha256_file(registry),
            "registry_hash": envelope["registry_hash"],
        },
        "report": {
            "path": "report.json",
            "sha256": sha256_file(report),
            "valid": report_value["valid"],
            "finalized_unclaimed": permission.get("finalized_unclaimed"),
            "complete_registry_claims": permission.get("complete_registry_claims"),
            "registry_hash": report_value.get("registry_hash"),
        },
        "windows": None,
    }
    manifest_path = dest / "manifest.json"
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    return {
        "dest": dest,
        "baseline": baseline,
        "manifest": manifest_path,
        "registry": registry,
        "report": report,
        "captures": captures,
        "proposals": proposals,
        "tool_manifest": tool_manifest_path,
        "artifact": artifact,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        sys.stderr.write("usage: fixture_builder.py <dest-dir>\n")
        return 2
    info = build_fixture(Path(argv[0]))
    sys.stdout.write(json.dumps({
        "manifest": str(info["manifest"]),
        "registry": str(info["registry"]),
        "report": str(info["report"]),
        "captures": str(info["captures"]),
    }, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
