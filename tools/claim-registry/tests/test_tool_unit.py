"""Tool-unit contract tests: describe, dependency fail-loud, manifest, build.

Covers DESIGN §1/§3: schema of ``--describe``, deterministic describe bytes,
works-without-tree-sitter, pinned dependencies, ``claim-run-manifest/1``
round-trip + tamper rejection, repeatable ``--proposals`` merge, deterministic
build, ``TOOL.json`` <-> describe consistency, and ``--check-pin``.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from toolkit import tool_unit

from claim_registry.cli import main
from claim_registry.tool_manifest import MANIFEST

UNIT_ROOT = Path(__file__).resolve().parents[1]
COMMON = UNIT_ROOT.parent / "common"
DIST = UNIT_ROOT / "dist"
PYZ_NAME = f"{MANIFEST['name']}-{MANIFEST['version']}.pyz"
PYZ = DIST / PYZ_NAME
TOOL_JSON = UNIT_ROOT / "TOOL.json"

SUBCOMMANDS = ("capture", "frame", "assemble", "validate", "windows", "hash", "manifest")


def _env(extra_path: str | None = None) -> dict:
    env = dict(os.environ)
    paths = []
    if extra_path:
        paths.append(str(extra_path))
    paths.append(str(COMMON))
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _run(args, **kwargs):
    return subprocess.run(
        [sys.executable, *args], cwd=UNIT_ROOT, capture_output=True, text=True, **kwargs
    )


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_describe_schema_and_determinism():
    first = _run(["-m", "claim_registry.cli", "--describe"], env=_env())
    second = _run(["-m", "claim_registry.cli", "--describe"], env=_env())
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout
    described = json.loads(first.stdout)

    assert described["schema_version"] == "tool-unit/1"
    assert described["name"] == "claim-registry"
    assert described["version"] == "0.3.0"
    assert described["requires_python"] == ">=3.11"
    assert described["artifact"] is None
    assert described["artifact_note"]
    assert tool_unit.describe_bytes(described) + b"\n" == first.stdout.encode("utf-8")

    for command in SUBCOMMANDS:
        assert command in described["commands"], f"missing command {command}"
        spec = described["commands"][command]
        assert spec["usage"], command
        assert spec["summary"], command
        assert spec["params"], command
        assert spec["outputs"], command
        assert set(spec["exit_codes"]) == {"0", "1", "2"}, command
        for param in spec["params"]:
            assert set(param) == {"name", "type", "required", "default", "description"}
            assert param["type"] in {"path", "string", "int", "flag"}

    assert set(described["exit_codes"]) == {"0", "1", "2"}
    assert described["exit_codes"]["0"] == "ok"
    assert "report.errors" in described["exit_codes"]["1"]
    assert described["exit_codes"]["2"].startswith("usage or environment")

    deps = {dep["name"]: dep for dep in described["dependencies"]}
    assert set(deps) == {"tree-sitter", "tree-sitter-markdown"}
    assert deps["tree-sitter"]["verified_version"] == "0.26.0"
    assert deps["tree-sitter"]["spec"] == "==0.26.0"
    assert deps["tree-sitter-markdown"]["verified_version"] == "0.5.1"
    assert deps["tree-sitter-markdown"]["spec"] == "==0.5.1"
    for dep in deps.values():
        assert dep["install"].startswith("python3 -m pip install ")
        assert f"{dep['name']}=={dep['verified_version']}" in dep["install"]

    pins = described["recipe_pins"]
    assert pins["canonicalization"] == "claim-json/1"
    assert "tree-sitter-markdown 0.5.1" == pins["parser"]
    assert "tree-sitter 0.26.0" == pins["runtime"]
    assert "claim-registry-frame/1" == pins["frame_recipe"]
    assert "max_units=64" in pins["window_recipe"]


def test_describe_without_tree_sitter_and_command_fails_loud(tmp_path):
    shim_root = tmp_path / "shim"
    (shim_root / "tree_sitter").mkdir(parents=True)
    (shim_root / "tree_sitter" / "__init__.py").write_text(
        "raise ImportError('tree-sitter deliberately unavailable (test shim)')\n",
        encoding="utf-8",
    )
    env = _env(shim_root)

    probe = subprocess.run(
        [sys.executable, "-c", "import tree_sitter"], capture_output=True, text=True, env=env
    )
    assert probe.returncode != 0, "shim did not shadow the installed tree-sitter"

    describe = _run(["-m", "claim_registry.cli", "--describe"], env=env)
    assert describe.returncode == 0, describe.stderr
    assert json.loads(describe.stdout)["name"] == "claim-registry"

    body = tmp_path / "body.md"
    body.write_bytes(b"# T\n")
    frame = _run(
        ["-m", "claim_registry.cli", "frame", "--in", str(body), "--locator", "repo#17:body"],
        env=env,
    )
    assert frame.returncode == 2, frame.stdout
    assert "pip install" in frame.stderr
    assert "'tree-sitter==0.26.0'" in frame.stderr
    assert "'tree-sitter-markdown==0.5.1'" in frame.stderr


def test_manifest_end_to_end_golden(tmp_path, capsys, pr_body):
    from claim_registry.capture import SourceCapture
    from claim_registry.frame import frame_source
    from claim_registry.registry import default_proposals

    body = tmp_path / "body.md"
    body.write_bytes(pr_body)
    capdir = tmp_path / "captures"
    assert main(["capture", "--in", str(body), "--locator", "repo#17:body", "--out", str(capdir)]) == 0
    capsys.readouterr()

    cap = SourceCapture(locator="repo#17:body", source_class="api-document", data=pr_body)
    proposals = default_proposals(cap.source_ref, frame_source(pr_body))
    prop = tmp_path / "proposals.json"
    prop.write_text(json.dumps(proposals), encoding="utf-8")

    registry = tmp_path / "registry.json"
    assert main(["assemble", "--captures", str(capdir), "--proposals", str(prop),
                 "--out", str(registry)]) == 0
    capsys.readouterr()

    report_path = tmp_path / "report.json"
    assert main(["validate", "--registry", str(registry), "--captures", str(capdir),
                 "--report-out", str(report_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is True
    assert report["permission"]["finalized_unclaimed"] is True
    assert report["permission"]["complete_registry_claims"] is True

    manifest_path = tmp_path / "run-manifest.json"
    assert main(["manifest", "--captures", str(capdir), "--proposals", str(prop),
                 "--registry", str(registry), "--report", str(report_path),
                 "--out", str(manifest_path)]) == 0
    capsys.readouterr()

    raw = manifest_path.read_bytes()
    assert not raw.endswith(b"\n")
    manifest = tool_unit.json_read(manifest_path)
    assert manifest["schema_version"] == "claim-run-manifest/1"
    assert manifest["tool"]["name"] == "claim-registry"
    assert manifest["tool"]["version"] == "0.3.0"
    assert manifest["tool"]["describe_sha256"] == tool_unit.describe_sha256(MANIFEST)
    assert manifest["tool"]["artifact"] is None  # not running from a .pyz
    assert manifest["windows"] is None

    envelope = json.loads(registry.read_bytes().decode("utf-8"))
    assert manifest["captures"] == {
        "path": str(capdir),
        "manifest_sha256": _sha(capdir / "manifest.json"),
    }
    assert manifest["proposals"] == [{"path": str(prop), "sha256": _sha(prop)}]
    assert manifest["registry"] == {
        "path": str(registry),
        "sha256": _sha(registry),
        "registry_hash": envelope["registry_hash"],
    }
    assert manifest["report"]["path"] == str(report_path)
    assert manifest["report"]["sha256"] == _sha(report_path)
    assert manifest["report"]["valid"] is True
    assert manifest["report"]["finalized_unclaimed"] is True
    assert manifest["report"]["complete_registry_claims"] is True
    assert manifest["report"]["registry_hash"] == envelope["registry_hash"]

    # Tamper one byte (value preserved as JSON but hash no longer matches the
    # original): the manifest records the new sha -> gate-check mismatch basis.
    value_tampered = tmp_path / "registry-value-tampered.json"
    data = bytearray(registry.read_bytes())
    marker = b'"registry_hash":"'
    index = bytes(data).index(marker) + len(marker)
    data[index] = ord("0") if data[index] != ord("0") else ord("1")
    value_tampered.write_bytes(bytes(data))
    assert main(["manifest", "--captures", str(capdir), "--proposals", str(prop),
                 "--registry", str(value_tampered), "--out", str(tmp_path / "m2.json")]) == 0
    capsys.readouterr()
    tampered_manifest = tool_unit.json_read(tmp_path / "m2.json")
    assert tampered_manifest["registry"]["sha256"] != manifest["registry"]["sha256"]

    # Non-canonical bytes (one appended byte) -> exit 1.
    noncanonical = tmp_path / "registry-noncanonical.json"
    noncanonical.write_bytes(registry.read_bytes() + b"\n")
    code = main(["manifest", "--captures", str(capdir), "--proposals", str(prop),
                 "--registry", str(noncanonical), "--out", str(tmp_path / "m2b.json")])
    assert code == 1
    assert "canonical" in capsys.readouterr().err.lower()

    # Missing/unreadable input -> exit 2.
    code = main(["manifest", "--captures", str(capdir),
                 "--registry", str(tmp_path / "missing.json"),
                 "--out", str(tmp_path / "m3.json")])
    assert code == 2
    assert "missing.json" in capsys.readouterr().err


def test_assemble_repeatable_proposals(tmp_path, capsys):
    from claim_registry.capture import SourceCapture
    from claim_registry.frame import frame_source
    from claim_registry.registry import default_proposals

    src = b"# Title\n\nAlpha claim.\n\nBeta claim.\n"
    body = tmp_path / "body.md"
    body.write_bytes(src)
    capdir = tmp_path / "captures"
    assert main(["capture", "--in", str(body), "--locator", "repo#17:body",
                 "--out", str(capdir)]) == 0
    capsys.readouterr()

    cap = SourceCapture(locator="repo#17:body", source_class="api-document", data=src)
    assignments = default_proposals(cap.source_ref, frame_source(src))["assignments"]
    assert len(assignments) >= 2
    split = max(1, len(assignments) // 2)

    full = tmp_path / "p-full.json"
    first = tmp_path / "p1.json"
    second = tmp_path / "p2.json"
    full.write_text(json.dumps({"schema_version": "claim-proposals/1", "assignments": assignments}), encoding="utf-8")
    first.write_text(json.dumps({"schema_version": "claim-proposals/1", "assignments": assignments[:split]}), encoding="utf-8")
    second.write_text(json.dumps({"schema_version": "claim-proposals/1", "assignments": assignments[split:]}), encoding="utf-8")

    reg_single = tmp_path / "r-single.json"
    reg_multi = tmp_path / "r-multi.json"
    assert main(["assemble", "--captures", str(capdir), "--proposals", str(full),
                 "--out", str(reg_single)]) == 0
    capsys.readouterr()
    assert main(["assemble", "--captures", str(capdir), "--proposals", str(first),
                 "--proposals", str(second), "--out", str(reg_multi)]) == 0
    capsys.readouterr()
    assert reg_single.read_bytes() == reg_multi.read_bytes()

    # Duplicate ownership across merged files still fails in assembly.
    dup_out = tmp_path / "r-dup.json"
    assert main(["assemble", "--captures", str(capdir), "--proposals", str(first),
                 "--proposals", str(first), "--out", str(dup_out)]) == 1
    assert "double-owned" in capsys.readouterr().err


@pytest.fixture(scope="session")
def built_unit():
    env = _env()
    first = subprocess.run([sys.executable, "build.py"], cwd=UNIT_ROOT,
                           capture_output=True, text=True, env=env)
    assert first.returncode == 0, first.stderr
    sha_first = _sha(PYZ)
    second = subprocess.run([sys.executable, "build.py"], cwd=UNIT_ROOT,
                            capture_output=True, text=True, env=env)
    assert second.returncode == 0, second.stderr
    sha_second = _sha(PYZ)
    describe = subprocess.run([sys.executable, str(PYZ), "--describe"], cwd=UNIT_ROOT,
                              capture_output=True, text=True)
    assert describe.returncode == 0, describe.stderr
    return {
        "sha_first": sha_first,
        "sha_second": sha_second,
        "describe": describe.stdout,
    }


def test_build_determinism_and_tool_json_consistency(built_unit):
    assert built_unit["sha_first"] == built_unit["sha_second"]

    tool_json = json.loads(TOOL_JSON.read_bytes().decode("utf-8"))
    assert tool_json["artifact"]["file"] == f"dist/{PYZ_NAME}"
    assert tool_json["artifact"]["sha256"] == built_unit["sha_first"]
    assert tool_json["artifact"]["size"] == PYZ.stat().st_size

    describe_value = dict(tool_json)
    describe_value["artifact"] = None
    assert tool_unit.describe_bytes(describe_value) + b"\n" == built_unit["describe"].encode("utf-8")

    sha_line = (DIST / f"{PYZ_NAME}.sha256").read_text(encoding="utf-8")
    assert sha_line == f"{built_unit['sha_first']}  {PYZ_NAME}\n"


def test_check_pin_on_built_artifact(built_unit):
    ok = subprocess.run(
        [sys.executable, str(PYZ), "--check-pin", built_unit["sha_first"]],
        cwd=UNIT_ROOT, capture_output=True, text=True,
    )
    assert ok.returncode == 0, ok.stderr
    assert "pin ok" in ok.stderr

    bad = subprocess.run(
        [sys.executable, str(PYZ), "--check-pin", "0" * 64],
        cwd=UNIT_ROOT, capture_output=True, text=True,
    )
    assert bad.returncode == 1
    assert "mismatch" in bad.stderr


def test_built_pyz_frame_recipe_matches_source(tmp_path, built_unit):
    from claim_registry.frame import frame_recipe

    body = tmp_path / "body.md"
    body.write_bytes(b"# T\n\nAlpha claim.\n")
    proc = subprocess.run(
        [sys.executable, str(PYZ), "frame", "--in", str(body), "--locator", "repo#17:body"],
        cwd=UNIT_ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["recipe"] == frame_recipe()


def test_manifest_records_tool_manifest_pin(tmp_path, capsys, built_unit):
    from claim_registry.capture import SourceCapture
    from claim_registry.frame import frame_source
    from claim_registry.registry import default_proposals

    src = b"# Title\n\nAlpha claim.\n"
    body = tmp_path / "body.md"
    body.write_bytes(src)
    capdir = tmp_path / "captures"
    assert main(["capture", "--in", str(body), "--locator", "repo#17:body",
                 "--out", str(capdir)]) == 0
    capsys.readouterr()

    cap = SourceCapture(locator="repo#17:body", source_class="api-document", data=src)
    prop = tmp_path / "proposals.json"
    prop.write_text(json.dumps(default_proposals(cap.source_ref, frame_source(src))), encoding="utf-8")
    registry = tmp_path / "registry.json"
    assert main(["assemble", "--captures", str(capdir), "--proposals", str(prop),
                 "--out", str(registry)]) == 0
    capsys.readouterr()

    manifest_path = tmp_path / "run-manifest.json"
    assert main(["manifest", "--captures", str(capdir), "--proposals", str(prop),
                 "--registry", str(registry), "--tool-manifest", str(TOOL_JSON),
                 "--out", str(manifest_path)]) == 0
    capsys.readouterr()

    manifest = tool_unit.json_read(manifest_path)
    assert manifest["tool"] == {
        "name": "claim-registry",
        "version": "0.3.0",
        "describe_sha256": tool_unit.describe_sha256(MANIFEST),
        "artifact": {
            "file": f"dist/{PYZ_NAME}",
            "sha256": built_unit["sha_first"],
        },
    }


def test_self_hash_artifact_file_is_basename(built_unit, monkeypatch):
    import argparse

    from claim_registry import cli

    monkeypatch.setattr(sys, "argv", [str(PYZ)])
    block = cli._tool_block(argparse.Namespace(tool_manifest=None))
    assert block["artifact"] == {"file": PYZ_NAME, "sha256": built_unit["sha_first"]}


def test_manifest_pins_match_live_recipes():
    from claim_label_contract import slicing

    from claim_registry import cli
    from claim_registry.frame import frame_recipe
    from claim_registry.registry import DEFAULT_WINDOW_RECIPE
    from claim_registry.tool_manifest import (
        FRAME_SLICE_MAX_BYTES, FRAME_SLICE_MAX_INPUT_BYTES,
        FRAME_SLICE_MAX_SLICES, FRAME_SLICE_MAX_UNITS,
        FRAME_SLICE_OVERLAP_UNITS,
    )

    pins = MANIFEST["recipe_pins"]
    recipe = frame_recipe()
    assert pins["frame_recipe"] == f"{recipe['name']}/{recipe['version']}"
    assert pins["parser"] == f"{recipe['parser']} {recipe['parser_version']}"
    assert pins["runtime"] == f"{recipe['runtime']} {recipe['runtime_version']}"
    assert pins["canonicalization"] == "claim-json/1"
    assert (cli.WINDOW_MAX_UNITS, cli.WINDOW_MAX_BYTES, cli.WINDOW_OVERLAP_UNITS) == (
        DEFAULT_WINDOW_RECIPE["max_units"],
        DEFAULT_WINDOW_RECIPE["max_bytes"],
        DEFAULT_WINDOW_RECIPE["overlap_units"],
    )
    assert str(DEFAULT_WINDOW_RECIPE["max_units"]) in pins["window_recipe"]

    assert (cli.FRAME_SLICE_MAX_BYTES, cli.FRAME_SLICE_MAX_UNITS,
            cli.FRAME_SLICE_MAX_INPUT_BYTES, cli.FRAME_SLICE_OVERLAP_UNITS,
            cli.FRAME_SLICE_MAX_SLICES) == (
        FRAME_SLICE_MAX_BYTES, FRAME_SLICE_MAX_UNITS,
        FRAME_SLICE_MAX_INPUT_BYTES, FRAME_SLICE_OVERLAP_UNITS,
        FRAME_SLICE_MAX_SLICES,
    )
    assert slicing.DEFAULT_MAX_BYTES == FRAME_SLICE_MAX_BYTES
    assert slicing.DEFAULT_MAX_UNITS == FRAME_SLICE_MAX_UNITS
    assert slicing.DEFAULT_MAX_INPUT_BYTES == FRAME_SLICE_MAX_INPUT_BYTES
    assert slicing.DEFAULT_OVERLAP_UNITS == FRAME_SLICE_OVERLAP_UNITS
    assert slicing.DEFAULT_MAX_SLICES == FRAME_SLICE_MAX_SLICES
    for needle in (str(FRAME_SLICE_MAX_BYTES), str(FRAME_SLICE_MAX_UNITS),
                   str(FRAME_SLICE_MAX_INPUT_BYTES), str(FRAME_SLICE_OVERLAP_UNITS),
                   str(FRAME_SLICE_MAX_SLICES)):
        assert needle in pins["slice_recipe"]
