# cure-light agentic tool units — design of record (build stage)

Status: build-stage design. Staging root `/workspaces/chunkhound_workspace/cure-light-tools/`
is shaped as the future repo `tools/` directory; landing = copy into the cure-light
branch `mods/v1-both-ends-docs` (PR #17) after operator confirmation of the PR
scope-line change. Repo writes do not happen before that confirmation.

Sources: notebook pages `cure-light-agentic-tool-units`,
`claim-registry-pilot-producer`, `cure-light-claim-registry-determinism`,
`chunkhound-markdown-reuse-research`, `cure-light-v1-both-ends-architecture`;
spec `/workspaces/chunkhound_workspace/cure-light-claim-registry-spec.md`;
PR-branch doc `kernel/references/intake-and-scope.md` §0.3a.

## 0. Staging layout (== future `tools/`)

```
tools/
  README.md                     toolkit overview + agent invocation flow (coordinator)
  DESIGN.md                     this file
  common/
    toolkit/
      __init__.py
      tool_unit.py              shared describe/manifest/exit-code/dependency helpers
      canonical_json.py         vendored copy of claim-registry/claim_registry/canonical.py
    build_zipapp.py             deterministic single-artifact (.pyz) builder
    tests/
  claim-registry/               pilot producer (package, tests, build, dist, SKILL.md)
  gate-check/                   manifest+registry+report consistency gate
  census/                       changed-range census (§0.3a recipe)
```

Each unit directory is self-contained: source, `build.py`, `TOOL.json`,
`dist/<name>-<version>.pyz` (+ `.sha256`), `SKILL.md`, `tests/`.

## 1. Tool-unit contract (all units)

A unit is *pluggable* when an agent can: fetch one artifact by pin, verify it,
read its capabilities, run it, and interpret exit codes — with no other context.

1. **Self-describing.** `python3 <unit>.pyz --describe` prints canonical JSON
   (`tool-unit/1`):
   ```json
   {
     "schema_version": "tool-unit/1",
     "name": "claim-registry", "version": "0.2.0",
     "summary": "...", "requires_python": ">=3.11",
     "dependencies": [{"name": "tree-sitter", "verified_version": "0.26.0",
                       "spec": "==0.26.0", "install": "python3 -m pip install ..."}],
     "commands": {"<cmd>": {"usage": "tool <cmd> --x Y", "summary": "...",
        "params": [{"name": "--x", "type": "path|string|int|flag", "required": true,
                    "default": null, "description": "..."}],
        "outputs": {"<key or file>": "..."},
        "exit_codes": {"0": "...", "1": "...", "2": "..."}}},
     "exit_codes": {"0": "ok", "1": "semantic/validation failure; read report.errors (each names the exact unit_id/field)",
                    "2": "usage or environment (bad args, missing/wrong pinned dependency)"},
     "determinism": {"idempotent": true, "no_hidden_state": true,
                     "identical_inputs_to_identical_outputs": true, "notes": "..."},
     "recipe_pins": {"<name>": "..."},
     "artifact": null,
     "artifact_note": "TOOL.json carries artifact.sha256; all other fields must match --describe exactly"
   }
   ```
   `--describe` must not import heavy/tree-sitter code; it works with dependencies
   missing so the agent can learn what to install. Static output: no timestamps,
   paths, or environment values.

2. **TOOL.json.** Shipped next to the artifact; `describe` output plus
   `{"artifact": {"file": "dist/<name>-<version>.pyz", "sha256": "<64hex>", "size": N}}`.
   Exactly reproducible: rebuild ⇒ same artifact bytes ⇒ same sha256.
   Verify: `sha256sum <artifact>` vs `TOOL.json.artifact.sha256`; run
   `--check-pin <sha256>` (hashes the running artifact; 0 ok, 1 mismatch,
   2 not running from a file artifact).

3. **Pinned dependencies (tree-sitter story).** The grammar ships as a
   platform-specific C extension; it is *not* bundled. Units declare exact
   dependencies in `TOOL.json.dependencies`; every non-describe command calls
   `require_dependencies()` before work and fails loud with exit **2**, the
   missing/wrong package names, and the exact install command
   (`python3 -m pip install 'tree-sitter==0.26.0' 'tree-sitter-markdown==0.5.1'`).
   Exact-match policy: any other installed version is an error (determinism
   depends on the pinned runtime; `frame_recipe()` already pins it).

4. **CLI semantics.** File/JSON in → file/JSON out; idempotent; no hidden state;
   stdout carries a JSON summary (or the report); diagnostics on stderr.
   0 = ok; 1 = semantic/validation failure with actionable errors
   (naming exact `unit_id`/field/check); 2 = usage/environment.

5. **Per-unit `SKILL.md`**: when to run, exact commands, what to do with output,
   failure handling, and the rule *never hand-edit registry JSON / never compute
   IDs or hashes*.

6. **Run manifest.** Schema `claim-run-manifest/1`, canonical JSON, produced by
   `claim-registry manifest` from files on disk (never hand-written):
   records tool name/version/`describe_sha256`, artifact sha when known, and for
   each input artifact its path + sha256 + key hashes (registry hash, report
   validity flags). `gate-check` re-verifies it.

## 2. Common toolkit (`common/`)

`toolkit/tool_unit.py` (stdlib-only):

```python
EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
class UsageError(Exception): ...        # -> exit 2
class DependencyError(Exception): ...   # -> exit 2, carries install_hint
def build_manifest(*, name, version, summary, dependencies, commands,
                   requires_python=">=3.11", recipe_pins=None,
                   determinism=None, extra=None) -> dict
def describe_bytes(manifest) -> bytes           # canonical JSON, no trailing newline
def describe_sha256(manifest) -> str
def require_dependencies(dependencies) -> None  # exact version equality
def install_hint(dependencies) -> str
def run_describe(manifest, argv) -> int         # handles --describe/--check-pin; else returns None
def json_write(path, value, *, canonical=True) -> bytes
def json_read(path) -> Any                       # strict canonical reader (dup keys rejected)
def sha256_file(path) -> str
```

`toolkit/canonical_json.py` is a byte-identical copy of the producer's
`canonical.py` (kept in sync by a test that compares files); exposes
`canonical_dumps`, `canonical_loads`, `hash_bytes`, `registry_hash`,
`recipe_hash`, `assert_canonical_bytes`, `CanonicalizationError`.

`build_zipapp.py`:

```python
def build_zipapp(files: Mapping[str, bytes|str|Path], out_path) -> str  # returns sha256
```

Writes a deterministic zip: entries sorted by arcname, `ZIP_STORED`, fixed
`date_time=(1980,1,1,0,0,0)`, fixed external attrs, shebang
`#!/usr/bin/env python3\n`. Rebuild ⇒ identical sha256. Caller supplies
`__main__.py` as one of `files`.

## 3. Unit: claim-registry (producer) — changes only

Keep the verified frame/capture/canonical/registry/validator/windows logic
byte-for-byte in behavior; golden gates must not move.

New:
* `--describe` / `--check-pin` global flags (call `run_describe` before argparse).
* Dependencies: `tree-sitter==0.26.0`, `tree-sitter-markdown==0.5.1`; checked in
  `main()` for all subcommands except describe/check-pin/help.
* `manifest` command:
  `claim-registry manifest --captures DIR --proposals P [--registry R] [--report V]
   [--windows W] [--tool-manifest TOOL.json] --out M.json`.
  Computes sha256 for each present file, the capture-manifest sha256, registry
  `registry_hash` (from the canonical envelope), proposals sha256, and writes
  canonical `claim-run-manifest/1`. Missing files → 2; malformed → 1.
* `assemble --proposals` becomes repeatable (merge in CLI order; duplicate
  ownership still fails). Backwards compatible.
* `version` 0.2.0 (`pyproject.toml`, `__init__.__version__` if present).
* `build.py`, `dist/`, `TOOL.json`, `SKILL.md` per §1.
* Tests: describe schema; exact-module deps; check-pin (built artifact);
  TOOL.json ⇔ describe consistency; build determinism; manifest round-trip;
  multi-proposal merge; existing 90 tests stay green.

## 4. Unit: gate-check

Independent stdlib-only unit (`gate_check` package or module) verifying a
completed run. CLI:

```
gate-check check --manifest M.json [--registry R.json] [--report V.json]
                 [--captures DIR] [--proposals P.json] [--windows W.json]
                 [--tool-manifest TOOL.json] [--artifact PATH] [--base-dir DIR]
                 [--report-out OUT.json]
gate-check --describe | --check-pin SHA
```

Paths in the manifest resolve against `--base-dir` (default: the manifest's
directory), absolute paths unchanged. Checks (each emitted as
`{"id", "ok", "detail"}`; exit 0 only if all pass, else 1):

1. manifest canonical bytes + `claim-run-manifest/1` shape.
2. every recorded file exists and its sha256 recomputes.
3. registry: canonical bytes; `registry_hash` recompute; `recipe_hash` recompute;
   payload witness `complete == true`; zero pending/conflict/error counts.
4. report: parsed; `valid == true`; `permission.finalized_unclaimed == true`;
   `permission.complete_registry_claims == true`; every `checks[].ok == true`;
   report `registry_hash` == registry recompute (binds report to this registry).
5. captures (when present): capture manifest sha256; each raw file sha256 vs
   manifest record; `source_ref` recompute; registry payload `sources` records
   match the capture manifest.
6. tool pin (when `--tool-manifest`/`--artifact` given): name/version match;
   `describe_sha256` recompute from TOOL.json (TOOL.json minus `artifact`);
   artifact sha256 recompute.
7. proposals sha256 matches the manifest (audit binding only).
8. `--report-out` writes the JSON report (canonical); stdout same JSON.

Schema `gate-check-report/1`: `{valid, checks[], errors[], permission:
{finalized_unclaimed, complete_registry_claims}, inputs: {...hashes...}}`.

## 5. Unit: census (changed-range census, §0.3a)

Stdlib + `git` CLI only. Read-only over the subject; scratch outside the repo.

```
census run --repo PATH --base REF --subject REF --out CENSUS.json [--scratch DIR]
census check --census CENSUS.json --repo PATH [--scratch DIR]
census --describe | --check-pin SHA
```

Pinned recipe (recorded in the artifact, never varied silently):
```
git -C repo rev-parse --verify <ref>^{commit}                       # resolve OIDs
git -C repo diff --no-ext-diff --no-textconv --no-color \
    --diff-algorithm=myers --no-indent-heuristic --no-renames -U0 base..subject
git -C repo diff --no-ext-diff --no-textconv --name-status -z --no-renames base..subject
git -C repo diff --no-ext-diff --no-textconv --numstat -z --no-renames base..subject
git -C repo diff --no-ext-diff --no-textconv --stat --no-renames base..subject   # orientation only
git --version
```
Two-dot `base..subject` semantics, never merge-base. No rename detection in the
pilot (a rename is a delete+add); `--stat` is never a denominator.

Output schema `changed-range-census/1` (canonical JSON, no trailing newline):
```
{
  "schema_version": "changed-range-census/1",
  "recipe": {"version": "1", "git_version": "...", "flags": [...],
             "diff_algorithm": "myers", "no_renames": true, "context": 0},
  "identity": {"repo": "...", "base_ref": "...", "subject_ref": "...",
                "base_oid": "...", "subject_oid": "...", "head_oid": "...",
                "worktree_dirty": bool},
  "files": [ {"old_path", "new_path", "status", "old_blob", "new_blob",
               "old_mode", "new_mode"} ],
  "parents": [ {"parent_id", "old_path", "new_path", "kind": "lines",
                 "old_start": int, "old_count": int,
                 "new_start": int, "new_count": int,
                 "patch_sha256": "<sha256 of the raw -U0 diff header+hunk>"} ],
  "events": [ {"event_id", "kind": "binary|mode_change|submodule|symlink|delete_file|add_file|no_text",
                "old_path", "new_path", "old_blob", "new_blob", "old_mode", "new_mode",
                "evidence": {...}} ],
  "counts": {"files", "parents", "events", "unique_changed_lines": {"old", "new"},
              "by_status": {...}},
  "partition": {"ok": true, "checks": [{"id", "ok", "detail"}], "errors": []},
  "recipe_hash": "...", "census_hash": "..."
}
```
Rules:
* Parent unit = one `-U0` edit block (hunk) in the pinned diff. Identity:
  `(base_oid, subject_oid, old_path, new_path, old_start/count, new_start/count,
  patch_sha256)`; `parent_id = "p:" + sha256(canonical tuple)[:32]`.
* Events: binary file changes, mode-only changes, submodule (mode 160000)
  changes, symlink (mode 120000) changes/type changes, added/deleted files with
  no textual diff, "no newline" edge records when they carry the only evidence.
  A file may have both an event and line parents (e.g. mode change + edits);
  that is not double counting in the line partition.
* Line accounting: per file and side, hunk ranges are disjoint and
  within the blob's line count; `unique_changed_lines` = union over parents per
  side (sum across files). Binary/submodule/symlink files contribute events,
  not lines.
* Partition checks: patch stream reconciles with `--name-status -z` (every file
  in exactly one order-independent set); `sum(old_count)`/`sum(new_count)`
  reconcile with `--numstat -z` totals; every parent/event maps to a known
  file pair; no orphan/missing records; `--stat` ignored for counts.
* `recipe_hash` = sha256 of canonical `recipe`; `census_hash` = sha256 of the
  canonical payload excluding `census_hash` itself **and excluding the
  environment-varying identity observations** `identity.repo`,
  `identity.head_oid`, `identity.worktree_dirty`. Those fields stay in the
  artifact for audit; `census check` compares them as separate *observations*
  (never as hash inputs, never as pass/fail checks), so a dirty worktree, a
  moved HEAD, or a relocated clone cannot change `census_hash`. The hash
  therefore binds exactly: base/subject OIDs + refs + recipe + files +
  parents + events + counts + partition.
* Deterministic across runs and machines with the same git version; the git
  version is part of the recipe pin. `check` must not write into the repo.

## 6. Agent invocation flow (all-agentic)

Roles: **coordinator agent** (runs tools via bash, routes, adjudicates, merges;
sole writer of state) / **labeling children** (read frame/window output, return
proposals JSON only) / **tools** (compute and seal).

1. Fetch units by pin (raw URL at a pinned commit + `TOOL.json` sha256);
   `--check-pin`; install pinned deps if `--describe` says so.
2. `capture` each designated source → capture dir.
3. `frame` / `windows` per source; coordinator spawns labeling children with the
   unit/window data. Children return `claim-proposals/1` assignments only:
   they select unit_ids, write states/labels/rationales/role_refs; they never
   compute IDs/hashes, never write the registry.
4. `assemble` (all proposal files) → canonical registry + `manifest` →
   `claim-run-manifest/1`.
5. `validate` → exit 0 required; on exit 1 read `report.errors` (each names the
   exact unit/field), fix the proposals, rerun assemble+validate. Never edit
   registry JSON.
6. `gate-check check --manifest ...` → exit 0 = the mechanical
   `finalized_unclaimed` permission is granted; only then downstream V1 uses the
   registry. Exit 1 = no permission, verbatim error list.

## 7. Trust boundary (must stay mechanical / not agent-optional)

ID/span/hash creation, canonical registry bytes, witness recomputation,
`finalized_unclaimed` permission. Proposals are the only agent-authored input
(append-only). gate-check is the mechanical decision even though every tool is
agent-invoked.

## 8. Acceptance gates (must stay green; extended per unit)

* Producer copy: pytest suite green (90 existing + new); goldens 29+22 and
  56+11 strict; corpus smoke 918 bodies/0 errors; E2E validate witness 51/51 +
  `finalized_unclaimed: true`; tamper rejected.
* New: built `.pyz` runs the full E2E (describe → check-pin → capture →
  assemble → validate → manifest → gate-check) with exit 0; each tamper in the
  gate-check test matrix exits 1; census fixtures (multi-hunk, add/delete,
  binary, mode, submodule, symlink, CRLF, no-newline) partition exactly;
  `census check` reproduces `census_hash`; build determinism (same sha twice).

## 9. Landing — DONE (2026-09-24)

Landed on `mods/v1-both-ends-docs` (PR #17) as a single `tools:` commit: this
tree copied to repo `tools/`, built `dist/*.pyz` + `TOOL.json` checked in so
pin-fetch works from raw branch URLs, per-tool `SKILL.md`, `tools/README.md`,
and `tools/demo/e2e_claim_registry.sh`. Operator confirmed the declared-scope
change before landing; the PR body's out-of-scope line was revised accordingly
(new review state) and `docs/contract-adequacy-validation-plan.md` line 11
updated (tools shipped; F1–F10 campaign harness still pending) — a new
designated-source hash. `CHANGELOG.md` intentionally untouched.

Pre-landing evidence: relocation simulation at `/tmp/landing-sim/tools/` (73
files, caches stripped) — suites 7/100/26/48 green and the demo PASS from the
relocated copy; the repo `.gitignore` does not block `tools/**`.
