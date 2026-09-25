"""Real cross-artifact E2E: rebuilt producer ``.pyz`` -> gate-check.

Runs the sibling producer artifact
(``<tools>/claim-registry/dist/claim-registry-<TOOL.json version>.pyz``)
end-to-end in a temp dir (capture -> assemble with library-built default
proposals -> validate --report-out -> manifest) and feeds the emitted
``claim-run-manifest/1`` to ``gate-check check``.

Proposals are built by importing the producer package as a library with
``PYTHONPATH=<tools>/claim-registry`` (``SourceCapture``,
``frame_source``, ``default_proposals``).  The test is skipped only when the
producer artifact is absent.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

UNIT = Path(__file__).resolve().parents[1]
# Repo layout: <tools>/gate-check and <tools>/claim-registry are siblings.
PRODUCER_ROOT = UNIT.parent / "claim-registry"
PRODUCER_TOOL_JSON = PRODUCER_ROOT / "TOOL.json"
if PRODUCER_TOOL_JSON.is_file():
    _pin = json.loads(PRODUCER_TOOL_JSON.read_bytes())
    PRODUCER_PYZ = PRODUCER_ROOT / _pin["artifact"]["file"]
else:  # pragma: no cover - absent pin only gates the skip below
    PRODUCER_PYZ = PRODUCER_ROOT / "dist" / "claim-registry-0.3.0.pyz"

BODY = b"# Title\n\nAlpha claim.\n\n- item one\n"
LOCATOR = "repo#e2e:body"


def _run(cmd: list[str], cwd: Path,
         env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)


def _run_gate(*args) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(UNIT), env.get("PYTHONPATH", "")) if p
    )
    return subprocess.run(
        [sys.executable, "-m", "gate_check.cli", *(str(a) for a in args)],
        capture_output=True, text=True, cwd=str(UNIT), env=env,
    )


@pytest.mark.skipif(
    not PRODUCER_PYZ.is_file(), reason=f"producer artifact absent: {PRODUCER_PYZ}"
)
def test_real_producer_artifact_to_gate(tmp_path):
    body = tmp_path / "body.md"
    body.write_bytes(BODY)
    cap = tmp_path / "cap"
    proposals = tmp_path / "proposals.json"
    registry = tmp_path / "registry.json"
    report = tmp_path / "report.json"
    manifest = tmp_path / "manifest.json"
    pyz = str(PRODUCER_PYZ)

    capture = _run([sys.executable, pyz, "capture", "--in", str(body),
                    "--locator", LOCATOR, "--out", str(cap)], tmp_path)
    assert capture.returncode == 0, capture.stderr

    lib_env = dict(os.environ)
    lib_env["PYTHONPATH"] = str(PRODUCER_ROOT) + os.pathsep + lib_env.get("PYTHONPATH", "")
    script = (
        "import json, sys\n"
        "from claim_registry.capture import SourceCapture\n"
        "from claim_registry.frame import frame_source\n"
        "from claim_registry.registry import default_proposals\n"
        "src = open(sys.argv[1], 'rb').read()\n"
        "cap = SourceCapture(locator=sys.argv[2], source_class='api-document', data=src)\n"
        "props = default_proposals(cap.source_ref, frame_source(src))\n"
        "open(sys.argv[3], 'w').write(json.dumps(props))\n"
    )
    props = _run([sys.executable, "-c", script, str(body), LOCATOR, str(proposals)],
                 tmp_path, env=lib_env)
    assert props.returncode == 0, props.stderr

    assemble = _run([sys.executable, pyz, "assemble", "--captures", str(cap),
                     "--proposals", str(proposals), "--out", str(registry)], tmp_path)
    assert assemble.returncode == 0, assemble.stderr
    validate = _run([sys.executable, pyz, "validate", "--registry", str(registry),
                     "--captures", str(cap), "--report-out", str(report)], tmp_path)
    assert validate.returncode == 0, validate.stderr
    seal = _run([sys.executable, pyz, "manifest", "--captures", str(cap),
                 "--proposals", str(proposals), "--registry", str(registry),
                 "--report", str(report), "--out", str(manifest)], tmp_path)
    assert seal.returncode == 0, seal.stderr

    sealed = json.loads(manifest.read_bytes())
    assert sealed["schema_version"] == "claim-run-manifest/1"
    # Running from the .pyz self-hashes: artifact is an object, file is basename.
    assert sealed["tool"]["artifact"]["file"] == PRODUCER_PYZ.name
    assert "labeling" not in sealed

    gate = _run_gate("check", "--manifest", manifest)
    assert gate.returncode == 0, gate.stdout + gate.stderr
    result = json.loads(gate.stdout)
    assert result["valid"] is True
    assert result["permission"] == {
        "finalized_unclaimed": True,
        "complete_registry_claims": True,
    }

    if PRODUCER_TOOL_JSON.is_file():
        # Producer pin: exercises ``tool.describe_sha256`` recompute (artifact
        # normalized to null) and ``tool.artifact_sha256`` against real files.
        pinned = _run_gate(
            "check", "--manifest", manifest,
            "--tool-manifest", PRODUCER_TOOL_JSON,
            "--artifact", PRODUCER_PYZ,
        )
        assert pinned.returncode == 0, pinned.stdout + pinned.stderr
