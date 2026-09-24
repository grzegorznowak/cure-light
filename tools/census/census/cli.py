"""census CLI: ``run``, ``check``, ``--describe``, ``--check-pin``."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from toolkit import canonical_json, tool_unit

from . import gitio, model
from .recipe import SCHEMA_VERSION, manifest

CHECK_SCHEMA = "census-check/1"
_REQUIRED_ARTIFACT_KEYS = (
    "schema_version",
    "recipe",
    "identity",
    "files",
    "parents",
    "events",
    "counts",
    "partition",
    "recipe_hash",
    "census_hash",
)


class CensusError(tool_unit.UsageError):
    """Environment/usage problem (exit 2)."""


def _report_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_json.canonical_dumps(payload)).hexdigest()


def _observations(repo: str, identity: Any) -> dict:
    """Declared-vs-current identity observations (informational; never gates ok).

    ``repo``/``head_oid``/``worktree_dirty`` are excluded from ``census_hash``
    (see :func:`census.model.census_hash_projection`); this block keeps them
    visible for audit without turning a moved HEAD or a dirty worktree into a
    check failure.
    """
    fields = model.CENSUS_HASH_EXCLUDED_IDENTITY_FIELDS
    declared = (
        {field: identity.get(field) for field in fields}
        if isinstance(identity, dict)
        else None
    )
    error: str | None = None
    try:
        current: dict | None = {
            "repo": repo,
            "head_oid": gitio.head_oid(repo),
            "worktree_dirty": gitio.worktree_dirty(repo),
        }
    except gitio.GitError as exc:
        current = None
        error = str(exc)
    matches = (
        {field: declared[field] == current[field] for field in fields}
        if declared is not None and current is not None
        else None
    )
    out: dict = {
        "declared": declared,
        "current": current,
        "matches": matches,
        "note": "informational only; never part of ok",
    }
    if error is not None:
        out["error"] = error
    return out


def _reject_inside(path: Path, repo: str) -> None:
    real_path = Path(os.path.realpath(path))
    real_repo = Path(os.path.realpath(repo))
    if real_path == real_repo or real_repo in real_path.parents:
        raise CensusError(
            f"scratch dir {path} is inside the subject repo {repo}; "
            "choose a scratch outside the repo"
        )


def _prepare_scratch(scratch: str | None, repo: str, *, fresh: bool) -> Path:
    base: Path | None = None
    if scratch:
        base = Path(scratch)
        _reject_inside(base, repo)
        base.mkdir(parents=True, exist_ok=True)
    if fresh:
        if base is None:
            return Path(tempfile.mkdtemp(prefix="census-scratch-"))
        return Path(tempfile.mkdtemp(prefix="census-scratch-", dir=str(base)))
    if base is None:
        return Path(tempfile.mkdtemp(prefix="census-scratch-"))
    return base


def _payload_for_oids(
    repo: str,
    base_oid: str,
    subject_oid: str,
    base_ref: str,
    subject_ref: str,
    repo_label: str,
    scratch: Path,
) -> dict:
    version = gitio.git_version()
    (scratch / "git-version.txt").write_text(version + "\n", encoding="ascii")
    streams = gitio.diff_streams(repo, base_oid, subject_oid, scratch)
    return model.build_census(
        repo=repo,
        base_oid=base_oid,
        subject_oid=subject_oid,
        base_ref=base_ref,
        subject_ref=subject_ref,
        head_oid=gitio.head_oid(repo),
        worktree_dirty=gitio.worktree_dirty(repo),
        repo_label=repo_label,
        git_version=version,
        patch_bytes=streams.patch,
        name_status_bytes=streams.name_status,
        numstat_bytes=streams.numstat,
    )


def _cmd_run(args: argparse.Namespace) -> int:
    repo = os.path.abspath(args.repo)
    gitio.check_repo(repo)
    scratch = _prepare_scratch(args.scratch, repo, fresh=False)
    base_oid = gitio.resolve_commit(repo, args.base)
    subject_oid = gitio.resolve_commit(repo, args.subject)
    payload = _payload_for_oids(
        repo,
        base_oid,
        subject_oid,
        args.base,
        args.subject,
        repo,
        scratch,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tool_unit.json_write(out, payload)
    partition = payload["partition"]
    tool_unit.emit_json(
        {
            "schema_version": SCHEMA_VERSION,
            "census_hash": payload["census_hash"],
            "counts": payload["counts"],
            "partition": {"ok": partition["ok"], "errors": partition["errors"]},
            "out": str(out),
            "scratch": str(scratch),
        }
    )
    return tool_unit.EXIT_OK if partition["ok"] else tool_unit.EXIT_FAIL


def _cmd_check(args: argparse.Namespace) -> int:
    repo = os.path.abspath(args.repo)
    gitio.check_repo(repo)
    try:
        raw = Path(args.census).read_bytes()
    except OSError as exc:
        raise CensusError(f"cannot read census artifact {args.census}: {exc}") from exc

    checks: list[dict] = []
    report: dict = {
        "schema_version": CHECK_SCHEMA,
        "ok": False,
        "census_hash": None,
        "recomputed_census_hash": None,
        "observations": None,
        "checks": checks,
        "errors": [],
    }

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "ok": bool(ok), "detail": detail})

    def finish() -> int:
        report["errors"] = [f"{c['id']}: {c['detail']}" for c in checks if not c["ok"]]
        report["ok"] = all(c["ok"] for c in checks)
        tool_unit.emit_json(report)
        return tool_unit.EXIT_OK if report["ok"] else tool_unit.EXIT_FAIL

    try:
        artifact = canonical_json.canonical_loads(raw)
    except canonical_json.CanonicalizationError as exc:
        add("artifact_parse", False, f"cannot parse {args.census}: {exc}")
        return finish()

    add(
        "census_canonical_bytes",
        canonical_json.canonical_dumps(artifact) == raw,
        (
            "artifact bytes are canonical changed-range-census/1 JSON"
            if canonical_json.canonical_dumps(artifact) == raw
            else "artifact bytes are not canonical claim-json/1; regenerate with census run, never hand-edit"
        ),
    )

    schema_ok = isinstance(artifact, dict) and all(
        key in artifact for key in _REQUIRED_ARTIFACT_KEYS
    )
    if schema_ok:
        schema_ok = artifact.get("schema_version") == SCHEMA_VERSION
    add(
        "census_schema",
        schema_ok,
        f"schema_version={artifact.get('schema_version')!r}"
        if isinstance(artifact, dict)
        else "artifact is not a JSON object",
    )
    if not schema_ok or not isinstance(artifact, dict):
        return finish()

    report["census_hash"] = artifact.get("census_hash")
    declared_hash = artifact.get("census_hash")
    recomputed_hash = _report_hash(model.census_hash_projection(artifact))
    add(
        "census_hash",
        recomputed_hash == declared_hash,
        f"declared {declared_hash}, recomputed {recomputed_hash}",
    )

    recipe = artifact["recipe"]
    add(
        "recipe_hash",
        _report_hash(recipe) == artifact.get("recipe_hash"),
        f"declared {artifact.get('recipe_hash')}, recomputed {_report_hash(recipe)}",
    )

    version = gitio.git_version()
    add(
        "git_version",
        recipe.get("git_version") == version,
        f"artifact {recipe.get('git_version')!r}, repo {version!r}",
    )

    identity = artifact["identity"]
    report["observations"] = _observations(repo, identity)
    ok_oids = True
    try:
        gitio.resolve_oid(repo, identity["base_oid"])
        gitio.resolve_oid(repo, identity["subject_oid"])
    except (gitio.GitError, KeyError) as exc:
        ok_oids = False
        add("oids_resolve", False, str(exc))
    else:
        add(
            "oids_resolve",
            True,
            f"base {identity['base_oid']} and subject {identity['subject_oid']} resolve in {repo}",
        )

    if ok_oids:
        scratch = _prepare_scratch(args.scratch, repo, fresh=True)
        recomputed = _payload_for_oids(
            repo,
            identity["base_oid"],
            identity["subject_oid"],
            identity["base_ref"],
            identity["subject_ref"],
            identity["repo"],
            scratch,
        )
        report["recomputed_census_hash"] = recomputed["census_hash"]
        add(
            "counts",
            recomputed["counts"] == artifact["counts"],
            "counts reproduce"
            if recomputed["counts"] == artifact["counts"]
            else f"declared {artifact['counts']} != recomputed {recomputed['counts']}",
        )
        add(
            "partition",
            recomputed["partition"] == artifact["partition"],
            "partition reproduces"
            if recomputed["partition"] == artifact["partition"]
            else "partition differs from recomputation",
        )
        add(
            "records",
            recomputed["files"] == artifact["files"]
            and recomputed["parents"] == artifact["parents"]
            and recomputed["events"] == artifact["events"],
            "files/parents/events reproduce"
            if (
                recomputed["files"] == artifact["files"]
                and recomputed["parents"] == artifact["parents"]
                and recomputed["events"] == artifact["events"]
            )
            else "files/parents/events differ from recomputation",
        )
        add(
            "recipe_recompute",
            recomputed["recipe"] == recipe,
            "recipe reproduces"
            if recomputed["recipe"] == recipe
            else f"declared {recipe} != recomputed {recomputed['recipe']}",
        )
        add(
            "census_hash_recompute",
            recomputed["census_hash"] == artifact.get("census_hash"),
            f"declared {artifact.get('census_hash')}, recomputed {recomputed['census_hash']}",
        )
    return finish()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="census",
        description=(
            "Deterministic changed-range census (changed-range-census/1) over "
            "base..subject with the pinned two-dot git-diff recipe."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the pinned recipe and write the census")
    run.add_argument("--repo", required=True, help="subject git repository (read-only)")
    run.add_argument("--base", required=True, help="base ref (resolved to a commit)")
    run.add_argument("--subject", required=True, help="subject ref (resolved to a commit)")
    run.add_argument("--out", required=True, help="canonical census JSON output path")
    run.add_argument(
        "--scratch",
        default=None,
        help="raw stream scratch dir (default: fresh temp dir outside the repo)",
    )

    check = sub.add_parser("check", help="recompute and verify a census artifact")
    check.add_argument("--census", required=True, help="changed-range-census/1 artifact")
    check.add_argument("--repo", required=True, help="git repository holding the recorded OIDs")
    check.add_argument(
        "--scratch",
        default=None,
        help="parent dir for the fresh check scratch (default: system temp)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    described = tool_unit.run_describe(manifest(), args_list)
    if described is not None:
        return described
    parser = _build_parser()
    args = parser.parse_args(args_list)
    try:
        if args.command == "run":
            return _cmd_run(args)
        return _cmd_check(args)
    except tool_unit.UsageError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return tool_unit.EXIT_USAGE
    except gitio.GitError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return tool_unit.EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
