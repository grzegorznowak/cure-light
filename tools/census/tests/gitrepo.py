"""Temp-repo helpers: fully deterministic OIDs (fixed author/committer env)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

FIXED_ENV = {
    "GIT_AUTHOR_NAME": "census-tests",
    "GIT_AUTHOR_EMAIL": "census@example.invalid",
    "GIT_COMMITTER_NAME": "census-tests",
    "GIT_COMMITTER_EMAIL": "census@example.invalid",
    "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+0000",
}


def _env() -> dict:
    env = dict(os.environ)
    env.update(FIXED_ENV)
    return env


def git(repo, *args, check: bool = True, input_bytes: bytes | None = None):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        env=_env(),
        input=input_bytes,
        check=check,
    )


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        capture_output=True,
        env=_env(),
        check=True,
    )
    git(path, "config", "core.autocrlf", "false")
    git(path, "config", "user.name", "census-tests")
    git(path, "config", "user.email", "census@example.invalid")
    return path


def write(repo, rel: str, data) -> Path:
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)
    return path


def symlink(repo, rel: str, target: str) -> Path:
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    path.symlink_to(target)
    return path


def remove(repo, rel: str) -> None:
    path = Path(repo) / rel
    if path.is_dir() and not path.is_symlink():
        raise TypeError(f"{rel} is a directory")
    path.unlink()


def stage_all(repo) -> None:
    git(repo, "add", "-A")


def gitlink(repo, rel: str, oid: str) -> None:
    """Stage a gitlink entry (call *after* ``stage_all``; do not ``add -A`` again)."""
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{oid},{rel}")


def commit_staged(repo, message: str = "commit") -> str:
    git(repo, "commit", "-q", "-m", message)
    return rev(repo, "HEAD")


def commit(repo, message: str = "commit") -> str:
    stage_all(repo)
    return commit_staged(repo, message)


def rev(repo, ref: str) -> str:
    return git(repo, "rev-parse", ref).stdout.decode().strip()
