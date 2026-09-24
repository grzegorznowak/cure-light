"""Shared toolkit contract tests (builder determinism, describe/pin, deps)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from build_zipapp import build_zipapp, collect_tree, entry_py
from toolkit import tool_unit

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.dirname(HERE)
TOOLKIT = os.path.join(COMMON, "toolkit")
PRODUCER_CANONICAL = os.path.join(
    os.path.dirname(COMMON), "claim-registry", "claim_registry", "canonical.py"
)

MINI_CLI = """\
from toolkit import tool_unit

MANIFEST = tool_unit.build_manifest(
    name="mini", version="0.0.1", summary="test fixture",
    dependencies=[],
    commands={"hello": {"usage": "mini hello", "summary": "prints hi", "params": []}},
)


def main():
    code = tool_unit.run_describe(MANIFEST)
    if code is not None:
        return code
    print("hi")
    return tool_unit.EXIT_OK
"""


def _mini_files() -> dict:
    return {
        "__main__.py": entry_py("mini"),
        "mini.py": MINI_CLI,
        **collect_tree(TOOLKIT, prefix="toolkit"),
    }


def _run(*args, **kwargs):
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, **kwargs
    )


def test_canonical_copy_matches_producer_bytes():
    if not os.path.exists(PRODUCER_CANONICAL):
        pytest.skip("producer canonical.py not reachable")
    with open(PRODUCER_CANONICAL, "rb") as fh:
        producer = fh.read()
    with open(os.path.join(TOOLKIT, "canonical_json.py"), "rb") as fh:
        shared = fh.read()
    assert shared == producer, "toolkit/canonical_json.py drifted from producer canonical.py"


def test_build_zipapp_is_deterministic(tmp_path):
    files = _mini_files()
    a = build_zipapp(files, tmp_path / "mini-a.pyz")
    b = build_zipapp(files, tmp_path / "mini-b.pyz")
    assert a == b
    with open(tmp_path / "mini-a.pyz", "rb") as fh:
        assert fh.read(2) == b"#!"


def test_built_pyz_describe_and_check_pin(tmp_path):
    files = _mini_files()
    sha = build_zipapp(files, tmp_path / "mini.pyz")
    proc = _run(str(tmp_path / "mini.pyz"), "--describe")
    assert proc.returncode == 0, proc.stderr
    described = json.loads(proc.stdout)
    assert described["schema_version"] == "tool-unit/1"
    assert described["name"] == "mini"
    assert described["artifact"] is None
    assert tool_unit.describe_sha256(described) == tool_unit.sha256_bytes(
        tool_unit.describe_bytes(described)
    )

    ok = _run(str(tmp_path / "mini.pyz"), "--check-pin", sha)
    assert ok.returncode == 0, ok.stderr
    bad = _run(str(tmp_path / "mini.pyz"), "--check-pin", "0" * 64)
    assert bad.returncode == 1
    assert "mismatch" in bad.stderr

    run = _run(str(tmp_path / "mini.pyz"), "hello")
    assert run.returncode == 0
    assert run.stdout.strip() == "hi"


def test_check_pin_requires_a_pyz(tmp_path, capsys):
    manifest = tool_unit.build_manifest(
        name="mini", version="0.0.1", summary="t", dependencies=[], commands={}
    )
    code = tool_unit.run_describe(
        manifest, ["--check-pin", "0" * 64], argv0=str(tmp_path / "plain.py")
    )
    assert code == tool_unit.EXIT_USAGE
    assert "must run from the packaged .pyz" in capsys.readouterr().err


def test_require_dependencies_exact_match():
    # tree-sitter is present at the pinned version in the acceptance env.
    dep = {"name": "tree-sitter", "verified_version": "0.26.0"}
    tool_unit.require_dependencies([dep])  # must not raise
    bad = {"name": "tree-sitter", "verified_version": "9.99.99"}
    with pytest.raises(tool_unit.DependencyError) as exc:
        tool_unit.require_dependencies([bad])
    assert "9.99.99" in str(exc.value)
    hint = tool_unit.install_hint([dep])
    assert "pip install 'tree-sitter==0.26.0'" in hint


def test_describe_is_environment_free_and_stable():
    args = dict(
        name="x",
        version="1.0.0",
        summary="s",
        dependencies=[],
        commands={},
    )
    a = tool_unit.describe_bytes(tool_unit.build_manifest(**args))
    b = tool_unit.describe_bytes(tool_unit.build_manifest(**args))
    assert a == b and not a.endswith(b"\n")


def test_tool_json_carries_artifact_pin():
    manifest = tool_unit.build_manifest(
        name="x", version="1.0.0", summary="s", dependencies=[], commands={}
    )
    data = tool_unit.tool_json_bytes(
        manifest, artifact_file="dist/x-1.0.0.pyz", artifact_sha256="ab" * 32, artifact_size=7
    )
    parsed = json.loads(data)
    assert parsed["artifact"] == {
        "file": "dist/x-1.0.0.pyz",
        "sha256": "ab" * 32,
        "size": 7,
    }
    del parsed["artifact"]
    parsed["artifact"] = None
    assert tool_unit.describe_bytes(parsed) == tool_unit.describe_bytes(manifest)
