"""End-to-end census fixtures over deterministic temp repos."""

from __future__ import annotations

import json
from pathlib import Path

from toolkit import canonical_json

from census import cli

from gitrepo import (
    commit,
    commit_staged,
    git,
    gitlink,
    init_repo,
    remove,
    rev,
    stage_all,
    symlink,
    write,
)


def do_run(repo, base, subject, out: Path, scratch: Path) -> int:
    return cli.main(
        [
            "run",
            "--repo",
            str(repo),
            "--base",
            base,
            "--subject",
            subject,
            "--out",
            str(out),
            "--scratch",
            str(scratch),
        ]
    )


def census(tmp_path: Path, repo, base, subject, name: str = "c"):
    out = tmp_path / f"{name}.json"
    rc = do_run(repo, base, subject, out, tmp_path / f"{name}-scratch")
    payload = canonical_json.canonical_loads(out.read_bytes())
    return rc, payload


def counts(files=0, parents=0, events=0, old=0, new=0, a=0, d=0, m=0, t=0):
    return {
        "files": files,
        "parents": parents,
        "events": events,
        "unique_changed_lines": {"old": old, "new": new},
        "by_status": {"A": a, "D": d, "M": m, "T": t},
    }


def test_single_hunk(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\nc\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\nc\n")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=1, old=1, new=1, m=1)
    parent = payload["parents"][0]
    assert (parent["old_start"], parent["old_count"], parent["new_start"], parent["new_count"]) == (2, 1, 2, 1)
    assert payload["events"] == []


def test_multi_hunk(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "".join(f"L{i}\n" for i in range(1, 11)))
    base = commit(repo, "base")
    write(
        repo,
        "f.txt",
        "L1\nX2\nX3\nL4\nL5\nL6\nL7\nX8\nX9\nL10\n",
    )
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=2, old=4, new=4, m=1)
    hunks = [(p["old_start"], p["old_count"], p["new_start"], p["new_count"]) for p in payload["parents"]]
    assert hunks == [(2, 2, 2, 2), (8, 2, 8, 2)]


def test_add_text_file(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "keep.txt", "k\n")
    base = commit(repo, "base")
    write(repo, "added.txt", "a\nb\nc\n")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=1, old=0, new=3, a=1)
    assert payload["events"] == []
    file = payload["files"][0]
    assert file["status"] == "A" and file["old_path"] is None and file["new_path"] == "added.txt"
    assert payload["parents"][0]["old_count"] == 0


def test_delete_text_file(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "gone.txt", "x\ny\n")
    base = commit(repo, "base")
    remove(repo, "gone.txt")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=1, old=2, new=0, d=1)
    assert payload["events"] == []
    file = payload["files"][0]
    assert file["status"] == "D" and file["new_path"] is None
    assert payload["parents"][0]["new_count"] == 0


def test_pure_deletion(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\nc\nd\ne\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nd\ne\n")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=1, old=2, new=0, m=1)


def test_binary_add_and_modify(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "b.bin", b"\x00\x01base")
    base = commit(repo, "base")
    write(repo, "b.bin", b"\x00\x02changed")
    write(repo, "c.bin", b"\x00\x03new")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=2, events=2, a=1, m=1)
    assert [e["kind"] for e in payload["events"]] == ["binary", "binary"]
    assert payload["parents"] == []


def test_mode_only_chmod(tmp_path):
    repo = init_repo(tmp_path / "r")
    path = write(repo, "s.sh", "echo hi\n")
    base = commit(repo, "base")
    path.chmod(0o755)
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, events=1, m=1)
    assert [e["kind"] for e in payload["events"]] == ["mode_change"]
    assert payload["parents"] == []
    file = payload["files"][0]
    assert (file["old_mode"], file["new_mode"]) == ("100644", "100755")


def test_mode_change_with_edits(tmp_path):
    repo = init_repo(tmp_path / "r")
    path = write(repo, "s.sh", "echo hi\n")
    base = commit(repo, "base")
    path.chmod(0o755)
    write(repo, "s.sh", "echo bye\n")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=1, events=1, old=1, new=1, m=1)
    assert [e["kind"] for e in payload["events"]] == ["mode_change"]


def test_submodule_gitlink_change_and_add(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "keep.txt", "k\n")
    stage_all(repo)
    gitlink(repo, "sub", "1" * 40)
    base = commit_staged(repo, "base")
    gitlink(repo, "sub", "2" * 40)
    gitlink(repo, "sub2", "3" * 40)
    subject = commit_staged(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=2, events=2, a=1, m=1)
    kinds = sorted((e["kind"], e["new_path"] or e["old_path"]) for e in payload["events"])
    assert kinds == [("submodule", "sub"), ("submodule", "sub2")]
    assert payload["parents"] == []


def test_symlink_retarget(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "tgt_a", "a")
    write(repo, "tgt_b", "b")
    symlink(repo, "link", "tgt_a")
    base = commit(repo, "base")
    symlink(repo, "link", "tgt_b")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, events=1, m=1)
    assert [e["kind"] for e in payload["events"]] == ["symlink"]
    assert payload["parents"] == []


def test_type_change_regular_to_symlink(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "tgt", "t")
    write(repo, "thing", "regular\n")
    base = commit(repo, "base")
    remove(repo, "thing")
    symlink(repo, "thing", "tgt")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, events=1, t=1)
    file = payload["files"][0]
    assert file["status"] == "T"
    assert (file["old_mode"], file["new_mode"]) == ("100644", "120000")
    assert [e["kind"] for e in payload["events"]] == ["symlink"]
    assert payload["parents"] == []


def test_empty_file_add_and_delete(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "empty_del.txt", "")
    base = commit(repo, "base")
    remove(repo, "empty_del.txt")
    write(repo, "empty_add.txt", "")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=2, events=2, a=1, d=1)
    kinds = sorted(e["kind"] for e in payload["events"])
    assert kinds == ["add_file", "delete_file"]
    assert payload["parents"] == []


def test_crlf(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\r\nb\r\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\r\nB\r\n")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=1, old=1, new=1, m=1)


def test_no_trailing_newline(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "abc")
    base = commit(repo, "base")
    write(repo, "f.txt", "abc\n")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts(files=1, parents=1, old=1, new=1, m=1)


def test_paths_with_spaces_and_non_ascii(tmp_path):
    repo = init_repo(tmp_path / "r")
    rel = "dir with spaces/naïve file.txt"
    write(repo, rel, "one\n")
    base = commit(repo, "base")
    write(repo, rel, "two\n")
    subject = commit(repo, "subject")
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    file = payload["files"][0]
    assert file["new_path"] == rel and file["old_path"] == rel
    assert payload["parents"][0]["new_path"] == rel


def test_empty_commit(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "x\n")
    base = commit(repo, "base")
    git(repo, "commit", "-q", "--allow-empty", "-m", "empty")
    subject = rev(repo, "HEAD")
    assert base != subject
    rc, payload = census(tmp_path, repo, base, subject)
    assert rc == 0 and payload["partition"]["ok"]
    assert payload["counts"] == counts()
    assert payload["files"] == [] and payload["parents"] == [] and payload["events"] == []


def test_artifact_shape(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "b\n")
    subject = commit(repo, "subject")
    _, payload = census(tmp_path, repo, base, subject)
    assert set(payload) == {
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
    }
    assert payload["schema_version"] == "changed-range-census/1"
    assert payload["identity"]["base_oid"] == base
    assert payload["identity"]["subject_oid"] == subject
    assert payload["identity"]["head_oid"] == subject
    assert payload["recipe"]["diff_algorithm"] == "myers"
    assert payload["recipe"]["no_renames"] is True
    assert payload["recipe"]["context"] == 0
    assert payload["recipe"]["flags"][0].startswith("-c core.quotePath=false diff ")
    assert isinstance(payload["identity"]["worktree_dirty"], bool)
    raw = (tmp_path / "c.json").read_bytes()
    assert not raw.endswith(b"\n")


def test_deterministic_across_runs(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\n")
    subject = commit(repo, "subject")
    out_a, out_b = tmp_path / "a.json", tmp_path / "b.json"
    assert do_run(repo, base, subject, out_a, tmp_path / "s-a") == 0
    assert do_run(repo, base, subject, out_b, tmp_path / "s-b") == 0
    assert out_a.read_bytes() == out_b.read_bytes()
    data = json.loads(out_a.read_text())
    assert data["census_hash"] == data["census_hash"]


def test_run_scratch_inside_repo_rejected(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "b\n")
    subject = commit(repo, "subject")
    out = tmp_path / "c.json"
    rc = do_run(repo, base, subject, out, repo / "scratch")
    assert rc == 2
    assert not out.exists()
    assert not (repo / "scratch").exists()


def test_run_and_check_do_not_write_into_repo(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\n")
    subject = commit(repo, "subject")
    index_path = repo / ".git" / "index"
    before = index_path.read_bytes()
    out = tmp_path / "c.json"
    assert do_run(repo, base, subject, out, tmp_path / "scratch") == 0
    rc = cli.main(
        ["check", "--census", str(out), "--repo", str(repo), "--scratch", str(tmp_path / "chk")]
    )
    assert rc == 0
    assert index_path.read_bytes() == before


def test_no_text_event_for_hunkless_modify():
    from census import model, patchparse

    file = {
        "old_path": "f",
        "new_path": "f",
        "status": "M",
        "old_blob": "aa",
        "new_blob": "bb",
        "old_mode": "100644",
        "new_mode": "100644",
    }
    record = patchparse.PatchRecord(
        header_line=b"diff --git a/f b/f",
        header_candidates=("f",),
        old_token=None,
        new_token=None,
        missing_old=False,
        missing_new=False,
        kind="modify",
        is_binary=False,
        old_mode=None,
        new_mode=None,
        hunks=[],
        sha256="f" * 64,
    )
    events = model._events_for(file, [record], False, "b" * 40, "s" * 40)
    assert [e["kind"] for e in events] == ["no_text"]


def test_check_reproduces_and_detects_tamper(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\n")
    subject = commit(repo, "subject")
    out = tmp_path / "c.json"
    assert do_run(repo, base, subject, out, tmp_path / "scratch") == 0
    rc = cli.main(
        ["check", "--census", str(out), "--repo", str(repo), "--scratch", str(tmp_path / "check")]
    )
    assert rc == 0

    payload = canonical_json.canonical_loads(out.read_bytes())
    payload["counts"]["parents"] = 99
    out.write_bytes(canonical_json.canonical_dumps(payload))
    rc = cli.main(["check", "--census", str(out), "--repo", str(repo)])
    assert rc == 1


def test_check_requires_oids_in_repo(tmp_path):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "b\n")
    subject = commit(repo, "subject")
    out = tmp_path / "c.json"
    assert do_run(repo, base, subject, out, tmp_path / "scratch") == 0

    other = init_repo(tmp_path / "other")
    write(other, "z.txt", "z\n")
    commit(other, "other")
    rc = cli.main(["check", "--census", str(out), "--repo", str(other)])
    assert rc == 1


def _check(repo, out: Path, scratch: Path) -> int:
    return cli.main(
        ["check", "--census", str(out), "--repo", str(repo), "--scratch", str(scratch)]
    )


def test_census_hash_projection_excludes_identity_observations():
    from census import model

    payload = {
        "census_hash": "x" * 64,
        "identity": {
            "repo": "/somewhere",
            "base_ref": "main~1",
            "subject_ref": "main",
            "base_oid": "a" * 40,
            "subject_oid": "b" * 40,
            "head_oid": "c" * 40,
            "worktree_dirty": True,
        },
        "counts": {},
    }
    projected = model.census_hash_projection(payload)
    assert "census_hash" not in projected
    assert projected["identity"] == {
        "base_ref": "main~1",
        "subject_ref": "main",
        "base_oid": "a" * 40,
        "subject_oid": "b" * 40,
    }
    # non-mutating: artifact keeps the observations for audit
    assert payload["identity"]["repo"] == "/somewhere"
    assert payload["identity"]["worktree_dirty"] is True
    assert payload["census_hash"] == "x" * 64


def test_check_passes_when_worktree_becomes_dirty(tmp_path, capsys):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\n")
    subject = commit(repo, "subject")
    out = tmp_path / "c.json"
    assert do_run(repo, base, subject, out, tmp_path / "scratch") == 0
    payload = canonical_json.canonical_loads(out.read_bytes())
    assert payload["identity"]["worktree_dirty"] is False

    write(repo, "untracked.txt", "dirt\n")  # untracked file created after run
    capsys.readouterr()  # discard the earlier run summary
    rc = _check(repo, out, tmp_path / "check")
    report = canonical_json.canonical_loads(capsys.readouterr().out.encode())
    assert rc == 0
    assert report["ok"] is True
    assert report["census_hash"] == payload["census_hash"]
    assert report["recomputed_census_hash"] == payload["census_hash"]
    checks = {c["id"]: c for c in report["checks"]}
    assert checks["census_hash"]["ok"] is True
    assert checks["census_hash_recompute"]["ok"] is True
    assert report["observations"]["declared"]["worktree_dirty"] is False
    assert report["observations"]["current"]["worktree_dirty"] is True
    assert report["observations"]["matches"]["worktree_dirty"] is False


def test_run_hash_ignores_repo_path_spelling(tmp_path, capsys):
    real = init_repo(tmp_path / "real")
    write(real, "f.txt", "a\nb\n")
    base = commit(real, "base")
    write(real, "f.txt", "a\nB\n")
    subject = commit(real, "subject")
    link = tmp_path / "link"
    link.symlink_to(real)

    out_real = tmp_path / "real.json"
    out_link = tmp_path / "link.json"
    assert do_run(real, base, subject, out_real, tmp_path / "s-real") == 0
    assert do_run(link, base, subject, out_link, tmp_path / "s-link") == 0
    payload_real = canonical_json.canonical_loads(out_real.read_bytes())
    payload_link = canonical_json.canonical_loads(out_link.read_bytes())
    assert payload_real["identity"]["repo"] != payload_link["identity"]["repo"]
    assert payload_real["census_hash"] == payload_link["census_hash"]

    capsys.readouterr()  # discard the earlier run summaries
    rc = _check(real, out_link, tmp_path / "check")
    report = canonical_json.canonical_loads(capsys.readouterr().out.encode())
    assert rc == 0
    assert report["ok"] is True
    assert report["recomputed_census_hash"] == payload_link["census_hash"]
    assert report["observations"]["matches"]["repo"] is False


def test_check_passes_when_head_moves(tmp_path, capsys):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\n")
    subject = commit(repo, "subject")
    out = tmp_path / "c.json"
    assert do_run(repo, base, subject, out, tmp_path / "scratch") == 0

    write(repo, "extra.txt", "moved\n")
    moved = commit(repo, "moved")
    assert moved != subject

    capsys.readouterr()  # discard the earlier run summary
    rc = _check(repo, out, tmp_path / "check")
    report = canonical_json.canonical_loads(capsys.readouterr().out.encode())
    assert rc == 0
    assert report["ok"] is True
    assert report["observations"]["declared"]["head_oid"] == subject
    assert report["observations"]["current"]["head_oid"] == moved
    assert report["observations"]["matches"]["head_oid"] is False


def test_genuine_content_change_changes_hash_and_fails_check(tmp_path, capsys):
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\nc\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\nc\n")
    subject_one = commit(repo, "subject-one")
    out_one = tmp_path / "one.json"
    assert do_run(repo, base, subject_one, out_one, tmp_path / "s1") == 0
    payload_one = canonical_json.canonical_loads(out_one.read_bytes())

    # reset the subject branch and land a genuinely different diff
    git(repo, "reset", "-q", "--hard", base)
    write(repo, "f.txt", "A\nb\nc\n")
    subject_two = commit(repo, "subject-two")
    out_two = tmp_path / "two.json"
    assert do_run(repo, base, subject_two, out_two, tmp_path / "s2") == 0
    payload_two = canonical_json.canonical_loads(out_two.read_bytes())
    assert payload_two["identity"]["subject_oid"] != subject_one
    assert payload_one["census_hash"] != payload_two["census_hash"]
    assert payload_one["parents"] != payload_two["parents"]

    # drop the discarded subject commit: old census can no longer reproduce
    git(repo, "reflog", "expire", "--expire=now", "--all")
    git(repo, "gc", "--prune=now", "-q")
    capsys.readouterr()  # discard the earlier run summaries
    rc = _check(repo, out_one, tmp_path / "check")
    report = canonical_json.canonical_loads(capsys.readouterr().out.encode())
    assert rc == 1
    assert report["ok"] is False
    checks = {c["id"]: c for c in report["checks"]}
    assert checks["oids_resolve"]["ok"] is False
