"""Thin CLI acceptance test: capture -> frame -> assemble -> validate -> windows."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from claim_registry.cli import main
from claim_registry.registry import default_proposals
from claim_registry.frame import frame_source
from claim_registry.capture import SourceCapture

SRC_BYTES = b"# Title\n\nAlpha claim.\n\nBeta claim.\n"


def test_cli_roundtrip(tmp_path, capsys):
    src_path = tmp_path / "body.md"
    src_path.write_bytes(SRC_BYTES)
    capdir = tmp_path / "captures"
    reg_path = tmp_path / "registry.json"
    win_path = tmp_path / "windows.json"
    prop_path = tmp_path / "proposals.json"

    assert main(["capture", "--in", str(src_path), "--locator", "repo#17:body",
                 "--out", str(capdir)]) == 0
    out = capsys.readouterr().out
    assert "git-blob-sha256" in out

    assert main(["frame", "--in", str(src_path), "--locator", "repo#17:body",
                 "--out", str(tmp_path / "frame.json")]) == 0
    capsys.readouterr()
    frame_json = json.loads((tmp_path / "frame.json").read_text("utf-8"))
    assert frame_json["unit_count"] == 5
    assert frame_json["block_count"] == 3
    assert frame_json["separator_count"] == 2

    cap = SourceCapture(locator="repo#17:body", source_class="api-document",
                        data=SRC_BYTES)
    frame = frame_source(SRC_BYTES)
    proposals = default_proposals(cap.source_ref, frame)
    prop_path.write_text(json.dumps(proposals), encoding="utf-8")

    assert main(["assemble", "--captures", str(capdir), "--proposals", str(prop_path),
                 "--out", str(reg_path)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["witness_complete"] is True
    assert reg_path.read_bytes().endswith(b"}")  # canonical, no trailing newline

    assert main(["validate", "--registry", str(reg_path), "--captures", str(capdir)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is True
    assert report["permission"]["finalized_unclaimed"] is True

    assert main(["windows", "--registry", str(reg_path), "--out", str(win_path)]) == 0
    capsys.readouterr()
    manifests = json.loads(win_path.read_text("utf-8"))
    assert manifests["manifests"][0]["source_ref"] == cap.source_ref

    assert main(["validate", "--registry", str(reg_path), "--captures", str(capdir),
                 "--windows", str(win_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is True

    # hash command reproduces both digests
    assert main(["hash", "--in", str(reg_path)]) == 0
    hashes = json.loads(capsys.readouterr().out)
    assert hashes["registry_hash_matches"] is True
    assert hashes["recipe_hash_matches"] is True


def test_cli_module_entrypoint(tmp_path):
    src_path = tmp_path / "body.md"
    src_path.write_bytes(SRC_BYTES)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        [sys.executable, "-m", "claim_registry.cli", "frame", "--in", str(src_path),
         "--locator", "repo#17:body"],
        cwd=repo_root, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["block_count"] == 3


def test_cli_validate_fails_on_tampered_registry(tmp_path, capsys, pr_body):
    src_path = tmp_path / "body.md"
    src_path.write_bytes(SRC_BYTES)
    capdir = tmp_path / "captures"
    assert main(["capture", "--in", str(src_path), "--locator", "repo#17:body",
                 "--out", str(capdir)]) == 0
    capsys.readouterr()
    cap = SourceCapture(locator="repo#17:body", source_class="api-document",
                        data=SRC_BYTES)
    frame = frame_source(SRC_BYTES)
    props = default_proposals(cap.source_ref, frame)
    prop_path = tmp_path / "proposals.json"
    prop_path.write_text(json.dumps(props), encoding="utf-8")
    reg_path = tmp_path / "registry.json"
    assert main(["assemble", "--captures", str(capdir), "--proposals", str(prop_path),
                 "--out", str(reg_path)]) == 0
    capsys.readouterr()
    raw = bytearray(reg_path.read_bytes())
    raw[-1:] = b" \n"  # trailing whitespace/newline breaks canonical form
    reg_path.write_bytes(bytes(raw))
    assert main(["validate", "--registry", str(reg_path), "--captures", str(capdir)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is False
    assert report["permission"]["finalized_unclaimed"] is False
