"""Read-only git plumbing for the census unit.

Every invocation is ``git -C <repo> ...`` with ``GIT_OPTIONAL_LOCKS=0`` so the
subject repo is never written to (no index refresh, no locks).  Scratch files
live outside the repo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from toolkit import tool_unit

from .recipe import CONFIG_ARGS, NAME_STATUS_FLAGS, NUMSTAT_FLAGS, PATCH_FLAGS, STAT_FLAGS


class GitError(RuntimeError):
    """A git command failed or git is missing (-> exit 2 for run)."""


def require_git() -> str:
    """Locate the git CLI; fail loud (usage error, exit 2) when missing."""
    exe = shutil.which("git")
    if exe is None:
        raise tool_unit.UsageError(
            "git executable not found on PATH; census requires the git CLI "
            "(install git, ensure it is on PATH, then re-run)"
        )
    return exe


def _env() -> dict:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["LC_ALL"] = "C"
    return env


def _exec(args: Sequence[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_env(),
    )


def run_git(repo: str | Path, args: Sequence[str], *, check: bool = True) -> bytes:
    """Run ``git -C repo <args>``; raise :class:`GitError` unless ``check`` is false."""
    exe = require_git()
    proc = _exec([exe, "-C", str(repo), *args])
    if check and proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip() or proc.stdout.decode(
            "utf-8", "replace"
        ).strip()
        raise GitError(f"git {' '.join(args)} failed in {repo}: {detail}")
    return proc.stdout


def run_git_to_file(repo: str | Path, args: Sequence[str], out_path: Path) -> None:
    """Run ``git -C repo <args>`` streaming stdout straight into ``out_path``."""
    exe = require_git()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        proc = subprocess.run(
            [exe, "-C", str(repo), *args],
            stdout=fh,
            stderr=subprocess.PIPE,
            env=_env(),
        )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} failed in {repo}: {detail}")


def check_repo(repo: str | Path) -> None:
    exe = require_git()
    proc = _exec([exe, "-C", str(repo), "rev-parse", "--git-dir"])
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise tool_unit.UsageError(f"{repo} is not a git repository: {detail}")


def resolve_commit(repo: str | Path, ref: str) -> str:
    """Resolve ``<ref>^{commit}``; bad/missing refs are usage errors (exit 2)."""
    exe = require_git()
    proc = _exec([exe, "-C", str(repo), "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}"])
    out = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0 or not out:
        raise tool_unit.UsageError(
            f"cannot resolve {ref!r} as a commit in {repo} "
            "(recipe: git rev-parse --verify <ref>^{commit})"
        )
    return out


def resolve_oid(repo: str | Path, oid: str) -> str:
    """Verify a recorded object id still resolves to the same commit; raise GitError."""
    exe = require_git()
    proc = _exec([exe, "-C", str(repo), "rev-parse", "--verify", "--quiet", "--end-of-options", f"{oid}^{{commit}}"])
    out = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0 or not out:
        raise GitError(f"recorded commit {oid} does not resolve in {repo}")
    if out != oid:
        raise GitError(f"recorded commit {oid} resolves to {out} (repository rewritten?)")
    return out


def git_version() -> str:
    exe = require_git()
    proc = _exec([exe, "--version"])
    out = proc.stdout.decode("utf-8", "replace").strip()
    if proc.returncode != 0 or not out:
        raise GitError("git --version failed; census requires a working git CLI")
    return out


def head_oid(repo: str | Path) -> str | None:
    exe = require_git()
    proc = _exec([exe, "-C", str(repo), "rev-parse", "--verify", "--quiet", "--end-of-options", "HEAD^{commit}"])
    out = proc.stdout.decode("utf-8", "replace").strip()
    return out or None


def worktree_dirty(repo: str | Path) -> bool:
    """Informational ``git status --porcelain`` probe (never used for accounting)."""
    exe = require_git()
    proc = _exec([exe, "-C", str(repo), "status", "--porcelain"])
    if proc.returncode != 0:
        raise GitError(
            f"git status --porcelain failed in {repo}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return bool(proc.stdout.strip())


def tree_entries(repo: str | Path, commit: str) -> dict[str, tuple[str, str]]:
    """Return ``{path: (mode, oid)}`` for the full tree at ``commit``.

    One ``git ls-tree -r -z`` call instead of per-file lookups (O(D) bookkeeping
    by the script, not the agent).  ``-z`` keeps paths raw/unquoted.
    """
    out = run_git(repo, ["ls-tree", "-r", "-z", commit])
    entries: dict[str, tuple[str, str]] = {}
    for raw in (e for e in out.split(b"\0") if e):
        meta, _tab, path = raw.partition(b"\t")
        fields = meta.split()
        if len(fields) != 3 or not path:
            raise GitError(f"unexpected git ls-tree entry at {commit}: {raw[:120]!r}")
        try:
            key = path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GitError(f"non-UTF-8 path in tree {commit}: {path[:80]!r}") from exc
        entries[key] = (fields[0].decode("ascii"), fields[2].decode("ascii"))
    return entries


def blob_line_count(repo: str | Path, oid: str) -> int:
    """Stream ``git cat-file blob <oid>`` and count lines without holding the blob."""
    exe = require_git()
    proc = subprocess.Popen(
        [exe, "-C", str(repo), "cat-file", "blob", oid],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_env(),
    )
    assert proc.stdout is not None
    count = 0
    total = 0
    last = b""
    while True:
        chunk = proc.stdout.read(1 << 16)
        if not chunk:
            break
        count += chunk.count(b"\n")
        total += len(chunk)
        last = chunk[-1:]
    proc.stdout.close()
    stderr = proc.stderr.read().decode("utf-8", "replace").strip() if proc.stderr else ""
    if proc.stderr:
        proc.stderr.close()
    code = proc.wait()
    if code != 0:
        raise GitError(f"git cat-file blob {oid} failed in {repo}: {stderr}")
    if total and last != b"\n":
        count += 1
    return count


@dataclass
class Streams:
    """Raw diff streams; every byte is also mirrored into the scratch dir."""

    patch: bytes
    name_status: bytes
    numstat: bytes
    stat: bytes


def diff_streams(repo: str | Path, base_oid: str, subject_oid: str, scratch: Path) -> Streams:
    """Run the four pinned diff invocations (two-dot semantics) into scratch."""
    rng = f"{base_oid}..{subject_oid}"
    scratch.mkdir(parents=True, exist_ok=True)

    patch_path = scratch / "patch.diff"
    run_git_to_file(repo, [*CONFIG_ARGS, "diff", *PATCH_FLAGS, rng], patch_path)

    name_status = run_git(repo, [*CONFIG_ARGS, "diff", *NAME_STATUS_FLAGS, rng])
    (scratch / "name-status.z").write_bytes(name_status)

    numstat = run_git(repo, [*CONFIG_ARGS, "diff", *NUMSTAT_FLAGS, rng])
    (scratch / "numstat.z").write_bytes(numstat)

    stat = run_git(repo, [*CONFIG_ARGS, "diff", *STAT_FLAGS, rng])
    (scratch / "stat.txt").write_bytes(stat)

    return Streams(
        patch=patch_path.read_bytes(),
        name_status=name_status,
        numstat=numstat,
        stat=stat,
    )
