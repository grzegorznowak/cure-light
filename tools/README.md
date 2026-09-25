# cure-light agentic tool units

Pluggable, deterministic tool units for the cure-light pipeline. Agents
orchestrate, route, and adjudicate; the tools compute and seal. See `DESIGN.md`
for the full contract and rationale.

## Roster

| Unit | Artifact (pinned by sha256) | Deps | Role |
|------|------------------------------|------|------|
| `claim-registry` | `claim-registry-0.3.0.pyz` | `tree-sitter==0.26.0`, `tree-sitter-markdown==0.5.1` | capture → frame/frame-slices → assemble/proposal-reconcile → validate → manifest `/1`/`/2` |
| `gate-check` | `gate-check-0.2.0.pyz` | none (stdlib) | verify run-manifest `/1`/`/2` + registry + validation report + captures + sliced labeling replay; grants/denies `finalized_unclaimed` |
| `census` | `census-0.1.0.pyz` | `git` CLI | §0.3a changed-range census: parents/events, unique changed lines, partition integrity |

Each unit directory is self-contained: source, `tests/`, `build.py`,
`dist/<name>-<version>.pyz` (+ `.sha256`), `TOOL.json`, `SKILL.md`.
`common/` holds the shared `toolkit` helpers (stdlib only) and the
deterministic `.pyz` builder; every unit bundles the helpers into its own
artifact.

## Fetch, verify, pin (universal pattern)

```bash
PIN=<pinned-commit-sha>
BASE="https://raw.githubusercontent.com/<owner>/<repo>/$PIN/tools/<unit>"
curl -fsSL "$BASE/TOOL.json" -o TOOL.json
curl -fsSL "$BASE/dist/<unit>-<version>.pyz" -o <unit>.pyz
# 1. sha256(<unit>.pyz) must equal TOOL.json.artifact.sha256
# 2. the running artifact verifies itself:
python3 <unit>.pyz --check-pin "$(python3 -c 'import json;print(json.load(open("TOOL.json"))["artifact"]["sha256"])')"
# 3. read capabilities; install pinned deps if needed (fail-loud exit 2 otherwise):
python3 <unit>.pyz --describe
```

Every tool-unit output is idempotent file/JSON in → file/JSON out. Exit codes:
`0` ok, `1` semantic/validation failure (actionable errors naming the exact
unit_id/field/check), `2` usage/environment (bad args, missing/wrong pinned
dependency). Agents record the fetched tool version + sha256 (and the
`describe_sha256`) in the run manifest, so a later `gate-check` re-verifies the
same tool identity.

## Invocation flow (coordinator + labeling children)

1. **Fetch and verify** the units by pin (above). `claim-registry` needs its
   pinned tree-sitter deps; `gate-check` and `census` do not.
2. **Capture** every designated source verbatim (`claim-registry capture`;
   repeat `--in`/`--locator` for a batch — one manifest, records in CLI order,
   never overwritten).
   Designation/pointer rules stay in the kernel docs; the tool stores bytes,
   locator, hash, and synthetic blob OID.
3. **Frame/window** the sources (`claim-registry frame`, `windows`). Sources
   that exceed the full-label caps (≤16 KiB raw / ≤80 units / ≤64 KiB worker
   input) use the bounded sliced path instead: `frame-slices` frames each
   source once and writes byte-exact worker payloads (`frame-slice-input/1`),
   one per bounded slice with a ≤4-unit preceding overlap for seam audits.
   The coordinator spawns **labeling children**, one per source, window, or
   slice; each child receives the frame/window/payload JSON (unit ids, spans,
   kinds, exact text) and returns **only** its proposal document: a
   `claim-proposals/1` file for whole-source labeling, or a
   `slice-proposals/1` file for a slice (core assignments + one overlap vote
   per overlap non-separator + per-adjacency grouping votes + boundary).
   Children never run the tools, never compute IDs or hashes, never write the
   registry. Template: `claim-registry/references/labeling-child-prompt.md`.
4. **Assemble** once with every proposal file
   (`assemble --proposals a.json --proposals b.json --out registry.json`).
   For sliced runs, first merge the children deterministically:
   `proposal-reconcile --captures captures/ --slices slices/manifest.json
   --proposal child-*.json --out merged.json --report-out reconciliation.json`
   (fails loud, never majority/first-wins). Double ownership, unknown units,
   non-consecutive claims, and undeclared decomposition remainders fail here
   with the exact `unit_id`.
5. **Validate** (`validate --registry registry.json --captures captures/
   --report-out report.json`). Exit 0 is required. On exit 1, fix the
   *proposals* and rerun 4–5; never edit the registry JSON — it is a computed
   artifact and hand-edits break the canonical-bytes and hash checks.
6. **Seal the run** (`manifest --captures ... --registry ... --report ...
   --out run-manifest.json`). The producer records every input sha256, the
   registry hash, the report flags, and its own tool pin. A sliced run seals
   `claim-run-manifest/2` with a mandatory `labeling` block (frame-slices
   manifest, every child, merged proposals, reconciliation report) whose
   paths are run-relative; a sliced run is never representable as `/1`.
7. **Gate** (`gate-check check --manifest run-manifest.json`). Exit 0 means the
   mechanical permission `finalized_unclaimed` is granted. For `/2` the gate
   replays the labeling block (span identity, recipe partition/payload bytes,
   deterministic reconciliation, registry ownership/grouping/rationales);
   pass `--require-sliced` to reject a downgraded `/1` manifest. This is the
   only authority to consume the registry downstream; it is not
   agent-optional.

Census wiring: after the subject pull and before any split, the coordinator
runs `census run --repo <subject> --base <oid> --subject <oid> --out
census.json` and records `census_hash` + counts in the coverage manifest; a
later `census check` recomputes the same census from the pinned OIDs.

## Trust boundary

Agents author proposals only. ID/span/hash creation, canonical registry bytes,
witness recomputation, and the `finalized_unclaimed` gate decision stay
mechanical. Proposals are append-only agent input; registries/reports/manifests
are recomputed, never hand-edited.

## Build and test

```bash
for u in common claim-registry gate-check census; do (cd $u && python3 -m pytest tests/ -q); done
for u in claim-registry gate-check census; do (cd $u && python3 build.py); done   # deterministic: same sha on rebuild
demo/e2e_claim_registry.sh   # full built-artifact flow + golden assertions
```

The `.pyz` builds are reproducible (sorted entries, fixed timestamps, stored
uncompressed), so `TOOL.json` pins stay meaningful across rebuilds.
