"""Census model assembly: streams -> ``changed-range-census/1`` payload.

Denominators are parents (``-U0`` edit blocks) and events (metadata changes).
Line accounting is per file+side over parent ranges; counts are never inferred
from ``--stat`` (orientation only).  The payload is canonical JSON with
``recipe_hash`` and ``census_hash`` self-witnesses.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from toolkit import canonical_json

from . import gitio, patchparse
from .partition import check_partition, unique_changed_lines
from .recipe import SCHEMA_VERSION, build_recipe

#: status -> expected patch-record kinds (``T`` is a delete+add pair under --no-renames)
EXPECTED_KINDS = {
    "A": ["add"],
    "D": ["delete"],
    "M": ["modify"],
    "T": ["add", "delete"],
}


@dataclass
class NumStat:
    added: int | None
    deleted: int | None


def parse_name_status(data: bytes) -> dict[str, str]:
    """Parse ``--name-status -z`` into ``{path: status}`` (order-independent)."""
    parts = [p for p in data.split(b"\0") if p]
    if len(parts) % 2:
        raise patchparse.PatchParseError(
            f"malformed --name-status -z stream: {len(parts)} NUL-separated fields"
        )
    out: dict[str, str] = {}
    for i in range(0, len(parts), 2):
        status = parts[i].decode("ascii", "strict")
        try:
            path = parts[i + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise patchparse.PatchParseError(
                f"non-UTF-8 path in --name-status -z: {parts[i + 1][:80]!r}"
            ) from exc
        if status not in EXPECTED_KINDS:
            raise patchparse.PatchParseError(
                f"unsupported name-status code {status!r} for {path!r} "
                "(recipe pins --no-renames)"
            )
        if path in out:
            raise patchparse.PatchParseError(
                f"duplicate path in --name-status -z: {path!r}"
            )
        out[path] = status
    return out


def parse_numstat(data: bytes) -> dict[str, NumStat]:
    """Parse ``--numstat -z`` into ``{path: NumStat}`` (added/deleted may be None)."""
    out: dict[str, NumStat] = {}
    for entry in (e for e in data.split(b"\0") if e):
        fields = entry.split(b"\t", 2)
        if len(fields) != 3:
            raise patchparse.PatchParseError(
                f"malformed --numstat -z entry: {entry[:80]!r}"
            )
        try:
            path = fields[2].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise patchparse.PatchParseError(
                f"non-UTF-8 path in --numstat -z: {fields[2][:80]!r}"
            ) from exc
        added = None if fields[0] == b"-" else int(fields[0])
        deleted = None if fields[1] == b"-" else int(fields[1])
        if path in out:
            raise patchparse.PatchParseError(f"duplicate path in --numstat -z: {path!r}")
        out[path] = NumStat(added, deleted)
    return out


def _sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json.canonical_dumps(value)).hexdigest()


#: Identity observations recorded for audit but excluded from ``census_hash``:
#: they vary by checkout location, HEAD movement, and worktree dirtiness and
#: carry no diff-content evidence (the OIDs/refs stay hashed).
CENSUS_HASH_EXCLUDED_IDENTITY_FIELDS = ("repo", "head_oid", "worktree_dirty")


def census_hash_projection(payload: dict) -> dict:
    """The canonical view that ``census_hash`` binds.

    Drops ``census_hash`` itself and the environment-varying identity
    observations (:data:`CENSUS_HASH_EXCLUDED_IDENTITY_FIELDS`).  ``run`` and
    ``check`` must both hash through this projection so they cannot drift; the
    dropped fields stay in the artifact and are compared by ``check`` as
    informational observations only.
    """
    projected = {key: value for key, value in payload.items() if key != "census_hash"}
    identity = projected.get("identity")
    if isinstance(identity, dict):
        projected["identity"] = {
            key: value
            for key, value in identity.items()
            if key not in CENSUS_HASH_EXCLUDED_IDENTITY_FIELDS
        }
    return projected


def _resolve_record_path(
    record: patchparse.PatchRecord, inventory: dict[str, str]
) -> tuple[str | None, str | None]:
    tokens: list[str] = []
    if record.old_token:
        tokens.append(record.old_token)
    if record.new_token:
        tokens.append(record.new_token)
    tokens.extend(record.header_candidates)
    matches: list[str] = []
    for token in tokens:
        if token in inventory and token not in matches:
            matches.append(token)
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, (
            f"{record.kind} patch record has no path matching the --name-status "
            f"inventory (candidates: {tokens}, header: {record.header_line[:120]!r})"
        )
    return None, (
        f"{record.kind} patch record is ambiguous across inventory paths {matches}"
    )


def _is_metadata(old_mode: str | None, new_mode: str | None) -> bool:
    return old_mode in ("120000", "160000") or new_mode in ("120000", "160000")


def _events_for(
    file: dict,
    records: list[patchparse.PatchRecord],
    is_binary: bool,
    base_oid: str,
    subject_oid: str,
) -> list[dict]:
    old_mode = file["old_mode"]
    new_mode = file["new_mode"]
    record_shas = sorted(r.sha256 for r in records)
    events: list[dict] = []

    def add(kind: str, evidence: dict) -> None:
        event_id = "e:" + _sha256_canonical(
            [
                base_oid,
                subject_oid,
                kind,
                file["old_path"],
                file["new_path"],
                file["old_blob"],
                file["new_blob"],
                old_mode,
                new_mode,
            ]
        )[:32]
        events.append(
            {
                "event_id": event_id,
                "kind": kind,
                "old_path": file["old_path"],
                "new_path": file["new_path"],
                "old_blob": file["old_blob"],
                "new_blob": file["new_blob"],
                "old_mode": old_mode,
                "new_mode": new_mode,
                "evidence": evidence,
            }
        )

    if is_binary:
        add(
            "binary",
            {"detected_by": "patch-binary-marker", "record_sha256": record_shas},
        )
    if _is_metadata(old_mode, new_mode):
        kind = "submodule" if "160000" in (old_mode, new_mode) else "symlink"
        add(kind, {"detected_by": "mode", "record_sha256": record_shas})
    elif old_mode and new_mode and old_mode != new_mode:
        add(
            "mode_change",
            {
                "old_mode": old_mode,
                "new_mode": new_mode,
                "record_sha256": record_shas,
            },
        )
    if not events:
        status = file["status"]
        has_hunks = any(r.hunks for r in records)
        if status == "A" and not has_hunks:
            add(
                "add_file",
                {"detected_by": "no-text-diff", "record_sha256": record_shas},
            )
        elif status == "D" and not has_hunks:
            add(
                "delete_file",
                {"detected_by": "no-text-diff", "record_sha256": record_shas},
            )
        elif status == "M" and not has_hunks:
            add(
                "no_text",
                {"detected_by": "no-text-diff", "record_sha256": record_shas},
            )
    return events


def build_census(
    *,
    repo: str,
    base_oid: str,
    subject_oid: str,
    base_ref: str,
    subject_ref: str,
    head_oid: str | None,
    worktree_dirty: bool,
    repo_label: str,
    git_version: str,
    patch_bytes: bytes,
    name_status_bytes: bytes,
    numstat_bytes: bytes,
) -> dict:
    """Build the canonical payload (all sections except ``census_hash``)."""
    extraction_errors: list[str] = []
    patch_errors: list[str] = []
    hunk_errors: list[str] = []

    try:
        records = patchparse.parse_patch(patch_bytes)
    except patchparse.PatchParseError as exc:
        extraction_errors.append(f"patch stream: {exc}")
        records = []
    try:
        inventory = parse_name_status(name_status_bytes)
    except patchparse.PatchParseError as exc:
        extraction_errors.append(f"name-status: {exc}")
        inventory = {}
    try:
        numstat = parse_numstat(numstat_bytes)
    except patchparse.PatchParseError as exc:
        extraction_errors.append(f"numstat: {exc}")
        numstat = {}

    grouped: dict[str, list[patchparse.PatchRecord]] = {}
    for record in records:
        path, error = _resolve_record_path(record, inventory)
        if error:
            patch_errors.append(error)
        else:
            grouped.setdefault(path, []).append(record)  # type: ignore[arg-type]

    for path, status in sorted(inventory.items()):
        expected = sorted(EXPECTED_KINDS[status])
        actual = sorted(r.kind for r in grouped.get(path, []))
        if not actual:
            patch_errors.append(
                f"file {path!r} is in --name-status ({status}) but has no patch record"
            )
        elif actual != expected:
            patch_errors.append(
                f"file {path!r} status {status} expects patch kinds {expected}, got {actual}"
            )
    for path in sorted(grouped):
        if path not in inventory:
            patch_errors.append(
                f"file {path!r} has patch records but is absent from --name-status"
            )

    files: list[dict] = []
    parents: list[dict] = []
    events: list[dict] = []
    needed_blobs: set[str] = set()

    try:
        base_tree = gitio.tree_entries(repo, base_oid)
        subject_tree = gitio.tree_entries(repo, subject_oid)
    except gitio.GitError as exc:
        extraction_errors.append(str(exc))
        base_tree = {}
        subject_tree = {}

    for path in sorted(inventory):
        status = inventory[path]
        old_ok = status != "A"
        new_ok = status != "D"
        old_entry = base_tree.get(path) if old_ok else None
        new_entry = subject_tree.get(path) if new_ok else None
        if old_ok and old_entry is None:
            extraction_errors.append(
                f"base tree lacks {path!r} (name-status {status})"
            )
        if new_ok and new_entry is None:
            extraction_errors.append(
                f"subject tree lacks {path!r} (name-status {status})"
            )
        old_mode, old_blob = old_entry if old_entry else (None, None)
        new_mode, new_blob = new_entry if new_entry else (None, None)
        file_records = grouped.get(path, [])
        is_binary = any(r.is_binary for r in file_records)
        file = {
            "old_path": path if old_ok else None,
            "new_path": path if new_ok else None,
            "status": status,
            "old_blob": old_blob,
            "new_blob": new_blob,
            "old_mode": old_mode,
            "new_mode": new_mode,
        }
        files.append(file)

        for record in file_records:
            for hunk in record.hunks:
                if hunk.old_lines != hunk.old_count:
                    hunk_errors.append(
                        f"{path}: hunk @@ -{hunk.old_start},{hunk.old_count} body has "
                        f"{hunk.old_lines} old lines"
                    )
                if hunk.new_lines != hunk.new_count:
                    hunk_errors.append(
                        f"{path}: hunk @@ +{hunk.new_start},{hunk.new_count} body has "
                        f"{hunk.new_lines} new lines"
                    )

        events.extend(_events_for(file, file_records, is_binary, base_oid, subject_oid))

        if is_binary or _is_metadata(old_mode, new_mode):
            continue
        for record in file_records:
            for hunk in record.hunks:
                parent_id = "p:" + _sha256_canonical(
                    [
                        base_oid,
                        subject_oid,
                        file["old_path"],
                        file["new_path"],
                        hunk.old_start,
                        hunk.old_count,
                        hunk.new_start,
                        hunk.new_count,
                        record.sha256,
                    ]
                )[:32]
                parents.append(
                    {
                        "parent_id": parent_id,
                        "old_path": file["old_path"],
                        "new_path": file["new_path"],
                        "kind": "lines",
                        "old_start": hunk.old_start,
                        "old_count": hunk.old_count,
                        "new_start": hunk.new_start,
                        "new_count": hunk.new_count,
                        "patch_sha256": record.sha256,
                    }
                )
                if hunk.old_count > 0 and old_blob:
                    needed_blobs.add(old_blob)
                if hunk.new_count > 0 and new_blob:
                    needed_blobs.add(new_blob)

    blob_lines: dict[str, int] = {}
    for oid in sorted(needed_blobs):
        try:
            blob_lines[oid] = gitio.blob_line_count(repo, oid)
        except gitio.GitError as exc:
            extraction_errors.append(str(exc))

    parents.sort(
        key=lambda p: (
            p["old_path"] or "",
            p["new_path"] or "",
            p["old_start"],
            p["old_count"],
            p["new_start"],
            p["new_count"],
            p["parent_id"],
        )
    )
    events.sort(key=lambda e: e["event_id"])

    counts = {
        "files": len(files),
        "parents": len(parents),
        "events": len(events),
        "unique_changed_lines": unique_changed_lines(parents),
        "by_status": {
            status: sum(1 for f in files if f["status"] == status)
            for status in ("A", "D", "M", "T")
        },
    }

    partition = check_partition(
        files=files,
        parents=parents,
        events=events,
        counts=counts,
        inventory=inventory,
        numstat={path: {"added": n.added, "deleted": n.deleted} for path, n in numstat.items()},
        extraction_errors=extraction_errors,
        patch_errors=patch_errors,
        hunk_errors=hunk_errors,
        blob_lines=blob_lines,
    )

    recipe = build_recipe(git_version)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "recipe": recipe,
        "identity": {
            "repo": repo_label,
            "base_ref": base_ref,
            "subject_ref": subject_ref,
            "base_oid": base_oid,
            "subject_oid": subject_oid,
            "head_oid": head_oid,
            "worktree_dirty": worktree_dirty,
        },
        "files": files,
        "parents": parents,
        "events": events,
        "counts": counts,
        "partition": partition,
        "recipe_hash": _sha256_canonical(recipe),
    }
    payload["census_hash"] = _sha256_canonical(census_hash_projection(payload))
    return payload
