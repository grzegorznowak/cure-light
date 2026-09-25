"""CLI contract: describe, check-pin, usage failures, git-missing path."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from toolkit import canonical_json

from census import cli

from gitrepo import commit, init_repo, write

UNIT = Path(__file__).resolve().parents[1]
COMMON = UNIT.parent / "common"


def test_describe_static(capsys):
    rc = cli.main(["--describe"])
    assert rc == 0
    payload = canonical_json.canonical_loads(capsys.readouterr().out.encode("utf-8"))
    assert payload["schema_version"] == "tool-unit/1"
    assert payload["name"] == "census"
    assert payload["version"] == "0.1.0"
    assert payload["artifact"] is None
    assert set(payload["commands"]) == {"run", "check"}
    assert payload["dependencies"] == []
    assert "changed-range-census" in payload["recipe_pins"]


def test_check_pin_dev_invocation_is_usage_error(capsys):
    rc = cli.main(["--check-pin", "0" * 64])
    assert rc == 2
    assert "pyz" in capsys.readouterr().err


def test_git_missing_is_exit_2(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "b\n")
    subject = commit(repo, "subject")
    out = tmp_path / "c.json"
    code = (
        "import sys\n"
        "from census.cli import main\n"
        f"sys.exit(main(['run','--repo',{str(repo)!r},'--base',{base!r},"
        f"'--subject',{subject!r},'--out',{str(out)!r}]))\n"
    )
    env = {"PATH": "/nonexistent", "PYTHONPATH": f"{UNIT}:{COMMON}"}
    proc = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True
    )
    assert proc.returncode == 2
    assert b"git" in proc.stderr.lower()
    assert not out.exists()


def test_describe_works_without_git():
    code = (
        "import sys\n"
        "from census.cli import main\n"
        "sys.exit(main(['--describe']))\n"
    )
    env = {"PATH": "/nonexistent", "PYTHONPATH": f"{UNIT}:{COMMON}"}
    proc = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True
    )
    assert proc.returncode == 0
    assert b"tool-unit/1" in proc.stdout


def test_not_a_repo_is_exit_2(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    rc = cli.main(
        [
            "run",
            "--repo",
            str(plain),
            "--base",
            "HEAD",
            "--subject",
            "HEAD",
            "--out",
            str(tmp_path / "c.json"),
        ]
    )
    assert rc == 2


def test_bad_ref_is_exit_2(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\n")
    commit(repo, "base")
    rc = cli.main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            "no-such-ref",
            "--subject",
            "HEAD",
            "--out",
            str(tmp_path / "c.json"),
        ]
    )
    assert rc == 2


def test_no_args_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2
