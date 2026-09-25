# census — skill snippet

Deterministic **changed-range census** (`changed-range-census/1`) for cure-light
Vector-1 coverage (Phase 0.3a). One fetchable artifact: `census-0.1.0.pyz` +
`TOOL.json` (pin `artifact.sha256`). Stdlib + the `git` CLI only; read-only over
the subject repo.

**Never hand-edit a census artifact. Regenerate it with `census run`.**

## When to run

- After the subject pull and immutable contract capture, **before** any split
  compile (0.3b) or Vector-1 spend — once per review state.
- Over that state's pinned `base_oid..subject_oid`, **two-dot** semantics only
  (never a merge-base substitution).
- On a re-pull, the state has new OIDs: recompute; never reuse a census across
  states.

## Fetch + verify

```bash
sha256sum census-0.1.0.pyz                 # compare with TOOL.json artifact.sha256
python3 census-0.1.0.pyz --check-pin <sha256>
python3 census-0.1.0.pyz --describe        # commands, params, exit codes, recipe pins
```

## Run

```bash
CENSUS_SCRATCH=/tmp/cure-<owner>-<pr>/census
python3 census-0.1.0.pyz run \
  --repo <subject_path> --base <base_oid> --subject <subject_oid> \
  --out  <CENSUS_SCRATCH>/census.json \
  --scratch <CENSUS_SCRATCH>/raw
```

- Scratch must be **outside** the subject repo (the tool refuses otherwise).
- `0` = ok, `partition.ok` is true.
- `1` = extraction/partition failure; the artifact is still written with
  `partition.ok=false` and `partition.errors` naming the check id + file/record.
- `2` = usage/environment: git missing from PATH, bad repo/ref, scratch inside
  the repo.
- Raw diff bytes go only to `--scratch` (`patch.diff`, `name-status.z`,
  `numstat.z`, `stat.txt`, `git-version.txt`); the artifact never embeds them.

## Check (independent reproduction)

```bash
python3 census-0.1.0.pyz check --census <CENSUS_SCRATCH>/census.json --repo <subject_path>
```

Recomputes the census in a fresh temp scratch with the **pinned recipe** and
verifies: canonical bytes, `census_hash`, `recipe_hash`, same `git --version`,
recorded OIDs still resolve, `counts`, `partition`, and files/parents/events.
`census_hash` is the sha256 of the canonical payload **excluding** the
environment-varying identity observations `identity.repo`,
`identity.head_oid`, `identity.worktree_dirty` (shared projection, so `run` and
`check` cannot drift): a dirty worktree, a moved HEAD, or a relocated clone
cannot change it. The report's top-level `observations` block echoes declared
vs current `repo`/`head_oid`/`worktree_dirty` and is **informational only —
never part of `ok`**. Exit `1` with `checks[]`/`errors[]` naming what diverged.
Read-only over the repo (no index refresh — `GIT_OPTIONAL_LOCKS=0`).

## What the output means

- `files[]` — `(old_path, new_path, status, old_blob, new_blob, old_mode,
  new_mode)` from `--name-status -z` + `git ls-tree`. A type change (`T`) is one
  file record (delete+add patch records merged).
- `parents[]` — **the changed-range denominator**: one entry per `-U0` edit
  block, with disjoint per-file+side ranges and `patch_sha256` content witness.
- `events[]` — metadata/no-text changes: `binary`, `mode_change`,
  `submodule` (160000), `symlink` (120000 / type change), `add_file` /
  `delete_file` (no textual diff), `no_text`. Events and line parents are
  independent accounting; a file can carry both (e.g. chmod + edits).
- `counts` — `files` / `parents` / `events` and `unique_changed_lines.{old,new}`
  (distinct touched line numbers per side, union of parent ranges, summed over
  files) plus `by_status`.
- `partition.checks[]` — `{id, ok, detail}`: patch ↔ `--name-status -z`,
  `--numstat -z` per-file **and** global line totals, hunk bounds/disjointness/
  body counts, parent/event file refs, full file coverage, counts recomputation.
  `--stat` is orientation only and is **never** a denominator.
- `identity` — OIDs, refs as given, `head_oid`, `worktree_dirty`
  (informational; `repo`/`head_oid`/`worktree_dirty` are excluded from
  `census_hash`). `recipe` — git version + verbatim flags; the git version is
  part of the recipe pin.
- Binary/submodule/symlink files contribute **events, not lines** (gitlink blobs
  are not readable and symlink/submodule `--numstat` rows are synthetic); their
  `--numstat` rows are claimed by the corresponding event and reported as
  exemptions in `numstat_counts`.

**No agent ingests the whole diff.** The tool does the O(D) enumeration/joins;
agents read bounded counts, IDs, and per-unit slices, and persist the full
ledger as a machine artifact, not in a model context.

## Failure handling

- Exit 1 → read `partition.errors`: each entry is `<check_id>: <detail>` and
  names the exact file/record (e.g. `numstat_counts: f.txt: parents sum old=2 …`).
  Fix the recipe/inputs (unparseable path, rename contradicting `--no-renames`,
  changed git version, shallow clone), then re-run. Never patch `CENSUS.json`.
- `git_version` mismatch in `check` → recompute under the pinned version before
  trusting the census.
- Exit 2 → install git / fix the repo or ref / move `--scratch` outside the repo.
