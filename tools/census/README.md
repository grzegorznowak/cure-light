# census — deterministic changed-range census (`changed-range-census/1`)

Second cure-light pluggable tool unit (after `claim-registry`). Streams the
pinned two-dot `git diff` recipe over `base_oid..subject_oid` into a scratch
dir, parses the `-U0` patch as a path-safe stream, reconciles it against
`--name-status -z` / `--numstat -z`, and writes one canonical JSON artifact:
parents (edit-block denominator), events (metadata changes), counts, and a
partition check that fails loud (exit 1) with actionable errors.

`census_hash` binds the canonical payload minus the environment-varying
identity observations (`identity.repo`, `identity.head_oid`,
`identity.worktree_dirty`), so the same diff keeps the same hash across dirty
worktrees, moved HEADs, and relocated checkouts; `check` reports those three as
an informational `observations` block (never part of `ok`).

Stdlib + the `git` CLI only; read-only over the subject repo; `--stat` is
orientation only, never a denominator. See [`SKILL.md`](SKILL.md) for the
operating recipe and [`../DESIGN.md`](../DESIGN.md) §5 for the normative schema.

## Layout

```
census/
  census/
    cli.py          run / check / --describe / --check-pin
    recipe.py       pinned recipe constants + tool-unit/1 manifest
    gitio.py        read-only git plumbing (GIT_OPTIONAL_LOCKS=0)
    patchparse.py   path-safe -U0 patch parser (records, hunks, spans)
    model.py        stream parsers + payload assembly (hashes, counts)
    partition.py    independent partition checker (pure functions)
  build.py          deterministic dist/census-0.1.0.pyz + TOOL.json + .sha256
  tests/            deterministic temp-git fixtures, partition unit tests
  SKILL.md          agent skill snippet
```

## Commands

```bash
python3 census/cli.py run   --repo R --base REF --subject REF --out C.json [--scratch DIR]
python3 census/cli.py check --census C.json --repo R [--scratch DIR]
python3 census/cli.py --describe | --check-pin SHA
```

Exit codes: `0` ok, `1` semantic/partition failure (`partition.errors` /
`checks[]` name the check and the record), `2` usage/environment (missing git,
bad repo/ref, scratch inside the repo).

## Dev / test / build

```bash
cd census
python3 -m pytest tests/ -q     # offline; deterministic temp repos under /tmp
python3 build.py                # dist/census-0.1.0.pyz + TOOL.json + .sha256
python3 dist/census-0.1.0.pyz --describe
```

Schema details, the git-version pin, and the binary/submodule/symlink
event-vs-lines accounting rule are documented in `SKILL.md`.
