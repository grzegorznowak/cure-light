# intake-and-scope.md — Phase 0: pull the subject, build the contract

Phase 0 runs once per **review state**. Its output is the **run manifest** — the single source of truth for every subsequent vector and the closure loop.

## The subject rule

cure-light reviews the tree it **pulls**, not the remote tip. Whatever SHA the pulled tree has at pull time is the version under review (reviewing the latest is desired, not a risk). The tree is stable for the whole state — nothing mutates it mid-run; a deliberate re-pull at an operator gate starts a **new review state** and updates the tree in place to the new head at that boundary (or pulls fresh when the tree is gone/broken, §0.1). A **contract-only repair** — the PR body/issue changed while no new code work was pulled — also opens a new review state with a recaptured contract snapshot; the tree itself is not re-pulled. An in-diff designated-source repair normally moves the subject OID even when executable code bytes are unchanged and is re-pulled as a new state on the new `base..subject` pair (both: closure-verification.md). Evidence is anchored to the subject; a state's findings never mix trees.

## 0.1 Pull the subject (preflight, ground truth)

**Subject-first.** Until the subject is pulled, nothing in the target repo's local checkouts is read or used for orientation — per review state (a deliberate re-pull starts a new state under the same rule). Pre-pull access is remote-only (`gh repo view` / `gh pr view` / `gh pr diff --name-only`) plus presence probes (chhound-driver.md §Presence); the only pre-pull local git command is the cure-light source provenance capture (§Output below). The pulled subject is the first tree cure-light reads for context or evidence.

At Phase 0:

- [ ] `gh auth status` — logged in, `repo` scope.
- [ ] `gh repo view <owner>/<repo>` reachable.
- [ ] `gh pr view <pr> --json headRefOid,baseRefOid,state,title` — PR exists and is OPEN; capture `baseRefOid` + the remote `headRefOid` as **informational context** (what gh reports now; NOT the subject).
- [ ] Pull the subject tree:
      - **re-pull, tree exists** (a new review state for a PR already pulled at `subject_path`) → update it **in place**: fetch the new head into the tree's repo and check it out detached (`git -C <subject_path> fetch …` + `git -C <subject_path> checkout --detach <new head>`). The rail sandbox needs no rail action: its live daemon re-indexes the sandbox automatically and the MCP bridge stays connected. A tree that is gone/broken (or a mechanism change) → pull fresh below.
      - **pi-chhound rail live** (chhound-driver.md §Presence) and no subject tree for this PR yet → create/connect the PR sandbox per [chhound-driver.md](chhound-driver.md) §Phase 0; the sandbox's worktree checkout is the subject.
      - **else** → plain detached worktree at the PR's current head, sourced as:
            - developer has an existing local clone of the target repo → source from that clone (fetch, then `git worktree add --detach <scratch>/tree <current headRefOid>`). Plumbing only — the clone is the git object source; its working tree is never read as context or evidence.
            - no local clone → clone the target repo into the review scratch dir (`git clone <target-url> <scratch>/tree`), fetch, then `git -C <scratch>/tree checkout --detach <current headRefOid>` — the clone is the subject.
      - `<scratch>` = the review scratch dir (e.g. `/tmp/cure-<owner>-<pr>/`); a fresh plain subject lands at `<scratch>/tree`, an in-place re-pull keeps the existing `subject_path`.
      - If the tree cannot be pulled at all, STOP (no evidence base).
- [ ] **Capture the subject**: `git -C <subject-path> rev-parse HEAD` → manifest `subject_oid`; the tree dir → `subject_path`. If `subject_oid` ≠ the gh-reported `headRefOid`, record both in the manifest — the pulled tree is the subject regardless (informational divergence, not an error). On an in-place re-pull the same `subject_path` gets the new `subject_oid`; the previous state's content stays reachable at its own OID (`git show <old_subject_oid>:<path>`).
- [ ] Complete the deferred requirements rows on the pulled tree (requirements-check.md rows 5/8/9) — the requirements check is complete only after this.
- [ ] (pi) `notebook_index` responds.
- [ ] (pi, optional) chhound index health (`{ch_prefix}_daemon_status`); fallback = bash/rg/grep. A broken index never blocks.

If any hard requirement fails: state the fallback (git/rg instead of chhound; plain worktree instead of sandbox; inherit-parent instead of fleet groups) or STOP before fleet cost.

## 0.2 Capture the contract

The contract lives in the **run store**: when the runtime's requirements check
confirms the notebook, Phase 0 writes it to the notebook page
`contract-<owner>-<pr>-s<n>` (one per review state, named like the frame page of
that state); otherwise create `CONTRACT.md` in a scratch review dir (e.g.
`/tmp/cure-<owner>-<pr>/`). The run manifest records `contract_ref` — the page
name, or the disk path in fallback runs.

The contract holds:
1. PR **description** — the claims the implementer makes (feature list, validation counts, behavior promises).
2. Linked **issues/tickets** — full text: bullets, tech context, **locked decisions** (verbatim operator decisions are the durable contract).
3. **Host tech context** worth grounding (existing APIs the PR builds on; caveats the issue itself records).
4. The **changed-file list**. (Per-child diff slices are derived at spawn time from the subject tree — `git diff base_oid..subject_oid -- <paths>` split per surface — and are not part of the stored contract.)
5. The captured **subject OID / base OID** and a note that everything below analyzes exactly the pulled subject tree at `subject_path`.

Rule: the contract is the captured sources' own words — the verbatim PR description/title and linked issue/locked decisions as today, plus any in-diff spec/design material the PR **explicitly designates** as intended source — never the reviewer's paraphrase of intent and never an unpointed lookalike. Preserve verbatim blocks.

### Designated in-diff sources

A pointer in the PR body, linked issue, or a locked decision may **explicitly designate** an in-diff spec/design file or package (an openspec-style change package, a changed design/spec doc) as a claim source. The explicit pointer is the trust stamp: repository convention (openspec layout, ADR folder, delta conventions) may **interpret** a designated package — which of its files are normative vs advisory, which clauses are the operative delta vs the retained baseline, how its roles fit — but convention alone never confers authority, and an unpointed spec-looking file, changed README, incidental design paragraph or test snapshot is ordinary changed documentation: evidence or context, never a claim source. Record per source block: source class, the designating pointer, the selection/interpretation rule plus any base-side policy citation, path/section, normative vs advisory status, and explicit precedence (if any). A pointed resource that cannot be captured and pinned is **context with a stated limitation**, never adjudicated as if read. When required designation or orientation is missing, record `repair_required` and leave the affected changed units unclaimed against the captured contract pending repair — never a reviewer-invented claim.

### Pin immutable source blocks

Pin per review state: `subject_oid` and `base_oid`, the subject-side blob OID for every selected source path (plus its base-side blob when a delta interpretation is needed), byte/hash and exact UTF-8 source spans, source role and selection rule — alongside separately timestamped/hash-snapshotted PR body/issue versions and the compiled registry's `registry_hash` + `claims_ref`/hash and the `gate-check` report ref/permission. **Dual identity pins are mandatory and distinct:** the producer's capture record supplies byte identity (raw `sha256`, `byte_length`, spans), while the repo-side identity is the actual git blob OID read from the pulled tree; an API document's synthetic `git-blob-sha256` is a producer-computed convenience, never a substitute for a repo blob OID, and a repo blob OID is never substituted for a captured-bytes hash. Source content is read from the pulled tree (`git show <subject_oid>:<path>`), never from a live edited checkout or the remote tip. A changed PR body/issue version or subject-side source blob mid-state is source drift: quarantine stale children/results and open a new state at the operator gate — no mixed-source findings.

### Compile the claim registry (pinned producer — mandatory, fail-closed)

The Phase-0 claim universe is computed by the engine's **own pinned tool copy**, never by a run-authored script: `claim-registry` **0.3.0** (tree-sitter producer), `gate-check` **0.2.0** (stdlib), `census` **0.1.0** (stdlib + git). The frame declares each version + sha256; fetch and `--check-pin`-verify the artifacts before use. **Subject-tree executables are never invoked — including the subject's own `tools/` and any demo — and the subject tree supplies no process code the run executes.** Zero run-authored compilers: no `registry2.py`-style script may author canonical registry bytes, unit/claim IDs, hashes, or permissions. Environment prerequisites (python ≥3.11, uv/venv, exact `tree-sitter==0.26.0` + `tree-sitter-markdown==0.5.1` installs) are declared at boot per requirements-check.md; a missing/wrong pinned dependency is a fail-loud exit 2.

Sequence over the state's designated, pinned source bytes (captured verbatim from bytes — no `gh --jq` shells, no trim/newline normalisation):

1. **Batch capture** every authorized source into one capture dir (`capture --in <src> --locator <locator>` repeatable, one manifest, records in CLI order, never overwritten). The manifest supplies byte identity (`sha256`, `byte_length`) plus the producer's synthetic `git-blob-sha256`; the repo-side blob OID is pinned independently (§Pin immutable source blocks).
2. **Frame once per source** and label the whole source when it is within the full-label caps: ≤16 KiB raw bytes, ≤80 units, and ≤64 KiB **complete serialized worker input** (pinned instructions + payload + prompt). Otherwise `frame-slices` frames each source once and writes bounded byte-exact worker payloads (`frame-slice-input/1`): ≤16 KiB raw text / ≤80 units / ≤64 KiB serialized input per slice, ≤4 preceding overlap units for seam audits, ≤32 slices by default; overlap-only slices are forbidden, and an oversized indivisible unit fails the run (never split). Raising the slice budget is an explicit recorded decision that changes the slice recipe/IDs — never a silent cap increase.
3. **Labeling children** (fleet-spawned; coordinator fallback per the stated budget) return only proposals: `claim-proposals/1` for whole-source labeling, or one `slice-proposals/1` per slice — primary assignments over core non-separators only, one audit vote per overlap non-separator, one grouping vote per visible non-separator adjacency pair, and the slice's left/right boundary declaration. Children never run the tools and never compute IDs/hashes (prompt template: `tools/claim-registry/references/labeling-child-prompt.md`).
4. **`proposal-reconcile`** merges the children deterministically: a differing audit rationale is retained as a warning; a state/subtype/role/grouping disagreement is a hard failure. A failed reconciliation publishes a failure report and never a usable merged artifact; the merged file is removed on failure so a stale success cannot be consumed.
5. **`assemble` → `validate` → `manifest`**: `validate` must exit 0; a sliced run seals `claim-run-manifest/2` with the mandatory `labeling` block (frame-slices manifest, every child, merged proposals, reconciliation report) and is never representable as `/1`.
6. **`gate-check check --require-sliced`** (plain `check` for a full-label run): exit 0 **and both permission flags** (`finalized_unclaimed`, `complete_registry_claims`) is the only authority to treat the registry as complete. On `/2` the gate replays the labeling block — span identity against captured bytes, recipe partition/payload bytes, deterministic reconciliation, and reconciled ownership/grouping/rationales against the registry.
7. **Project** the claims/coverage pages from the canonical registry — identical claim IDs, counts and `registry_hash`; the pages are queryable views, never a substitute, and window/slice IDs never become claim IDs (notebook-plan-contract.md).

```bash
python3 claim-registry-0.3.0.pyz frame-slices --captures captures/ --out-dir slices/ \
    --max-bytes 16384 --max-units 80 --max-input-bytes 65536 \
    --overlap-units 4 --max-slices 32
python3 claim-registry-0.3.0.pyz proposal-reconcile --captures captures/ \
    --slices slices/manifest.json --proposal children/0000.json \
    --out merged.json --report-out reconciliation.json
python3 claim-registry-0.3.0.pyz manifest --captures captures/ --slices slices/manifest.json \
    --slice-proposal children/0000.json --reconciliation reconciliation.json \
    --proposals merged.json --registry registry.json --report report.json --out run-manifest.json
python3 gate-check-0.2.0.pyz check --manifest run-manifest.json --require-sliced \
    --tool-manifest claim-registry-TOOL.json --artifact claim-registry-0.3.0.pyz
```

The early source-consistency pass (§Early source-consistency pass) runs after this sequence and before any V1 spend. Any pin mismatch, missing/wrong pinned dependency (exit 2), failed capture/frame/reconcile/assemble/validate/manifest/gate, or projection hash mismatch **stops Phase 0**: no hand-written fallback registry, no hand-added claim ID, no relaxed gate, no silent substitution of an older head.

The capture also compiles the **claim registry** — the state's complete claim universe — through the pinned producer (§Compile the claim registry above), never through run-authored IDs or scripts. Each claim ID and span comes from the producer's canonical `claim-json/1` registry, computed from the captured source bytes (block + exact byte `[start,end)` offsets + quote hash), with parent/group links (overlapping clauses keep explicit parent refs) and context/nonclaim labels, so section extraction cannot silently drop whole blocks. Each source block carries its class, designating pointer and interpretation rule (§Designated in-diff sources). Long contracts use the producer's bounded sliced path with overlap reconciliation; an incomplete source inventory means the claim universe is incomplete, and negative attribution cannot finalize from it. The complete claim directory is a **projection of the canonical registry** (identical claim IDs, counts and `registry_hash`) paged as the state's claim-registry page(s) (`claims-<owner>-<pr>-s<n>`, notebook-plan-contract.md), and the manifest records its `coverage.claims_ref`/hash plus the gate report/permission (Output below).

### Early source-consistency pass (before Vector 1)

After the registry is compiled from all designated, pinned sources and before any Vector 1 spend, run a **bounded within-source and cross-source consistency pass**: compare material purpose/scope/behavior-level declarations, not every phrasing difference. A **material unresolved contradiction** — within one source or between any pointed resources — without explicit/locked precedence is a description defect and is never reviewer-reconciled: record the exact conflicting quotes, offsets, source hashes and affected claim IDs, mark the state provisionally `repair_required`, and **default the run to pause before Vector 1**. Only an operator-recorded, named, bounded **evidence-only Vector 1 run** (scope/rationale/state) may proceed through that pause; the authorization gathers evidence and never clears the defect or authorizes ordinary downstream work. A **non-material wording inconsistency** is recorded as a defect without pausing. Author clarification or a repaired contract opens a new review state — not an in-place reconciliation. The pass settles source coherence only: the final `review_basis` is computed after Vector 1 (conformance-pass.md).

## 0.3 Split vectors into pass slices

### 0.3a Mechanical changed-range census

After the pinned producer run and before any split or the Phase-0 gate, the coordinator produces the **changed-range census** with the engine's pinned `census` unit (**0.1.0**, stdlib + git):

```bash
python3 census-0.1.0.pyz run --repo <subject_path> --base <base_oid> --subject <subject_oid> \
    --out <scratch>/census.json --scratch <scratch>/raw   # scratch outside the subject repo
python3 census-0.1.0.pyz check --census <scratch>/census.json --repo <subject_path>
```

Two-dot `base..subject` semantics only (never a merge-base substitution); `--stat` is orientation only, never the denominator. Parent units are the `git diff -U0` edit blocks; deletions, renames, mode/binary/submodule changes and other no-text edits are explicit metadata events with old/new path/blob or OID evidence. The artifact records parents/events counts, unique changed lines by side, the recipe + git version and the canonical `census_hash`; `census check` independently recomputes it under the pinned recipe. Exit 1 is a partition/extraction failure (`partition.ok:false` with `partition.errors`); exit 2 is usage/environment (git missing, bad refs, scratch inside the repo). No agent ingests the whole diff; contract-token ↔ path/symbol overlap may optionally yield candidate claim links (cheap, discovery-only); a missing candidate link never removes a unit from the denominator. Never hand-edit a census artifact, and never reuse one across review states — a re-pull has new OIDs and recomputes.

### 0.3b Capacity-bounded split compile

Each vector's fleet splits the contract surface, capacity-bounded within the approved budget. Example split for a model-group/spawn PR:

- conformance: contract surfaces (derivation core · persistence/schema guard · spawn/router gate · main-session+TUI · tests), each compiled into bounded claim/range shards — one verdict owner per claim, one accounting owner per unit — plus residual attribution shards for changed units with no candidate claim (work packaging only, never invented contracts)
- implementation: sealed concepts the review already established (never open-ended), + **`read` lens and the `blast` judgment rows** (the once-per-state sweep runs in the deterministic preflight)
- debt: pluggability · boundary ownership · versioning/migrations · projections · perf/operability, + **`dead`/`name`/`quality` lens ownership**

Slice granularity is chosen so each child reads a bounded file set + the relevant contract slice + only its ledger shard pages, and returns under a defined evidence budget.

The split compile asserts **Vector 1 coverage** — a verdict owner for every captured claim, an accounting owner for every eligible (non-excluded) changed unit — distinct from the lens assertion below. The lens matrix (hygiene-lens.md) is compiled here and validated: every active lens must map to ≥1 owner. Deterministic preflight (strict tsc / lint) is the `type` sweep and `dead` accelerant; it also produces the state's once-per-state `symbol_sweep` symbol map (recipe: chhound-driver.md, Symbol sweep) — consumed by the V2 splits for the `sweep` row, seeded into V3 debt and the yagni pass, and rendered as the comment's `Symbol impact`.

## 0.4 Operator gates

- **Plan gate (pre-pull).** Before Phase 0 mutates anything external, surface the compiled plan for confirmation: subject mechanism (chhound sandbox | plain worktree) and planned location, vectors, splits, groups, gates, output policy. The planned research mode (chhound-rail when the sandbox rail is planned, else direct-tree — pipeline-model.md) is part of the plan. The frame carries **no tree fields yet** — `subject_path` / `subject_oid` cannot exist before the pull (subject-first, §0.1).
- **Phase 0 gate (post-pull).** Surface the manifest with the recorded reality: actual `subject_path` / `subject_oid`, `base_oid`, changed-file list from the pulled tree, the census actual counts (parents/events + unique changed lines by side, completion flags) and the exclusion policy (evidence-linked classes — a path suffix alone is never sufficient), coverage-page location and budgets it approves, deferred requirements-row outcomes, fallback notes — a chhound-rail fallback (rail confirmed but sandbox pull/connect failed) also flips `research.mode` to `direct-tree` and `ch_prefix` to `none` (pipeline-model.md), so children render Variant B, never a rail variant whose tools are not connected — plus the **source-consistency outcome**: clean, recorded non-material inconsistency, or provisional `repair_required` with its contradiction records. A provisional `repair_required` defaults the run to **pause before Vector 1**: the operator requests author clarification/repair, or explicitly authorizes a named, bounded evidence-only Vector 1 run (recorded scope/rationale/state) that does not clear the defect or authorize ordinary downstream work. Thinness is judged across all explicitly designated, capturable sources — not PR-body length: a terse body with an accurate pointer to a complete designated package can pass; missing designation/orientation is `repair_required`; reviewer-invented claims are never an option. The repair-pause default applies to any `repair_required` defect (missing designation/orientation included), not just contradictions: the operator requests author repair, runs an explicitly limited V1-only review, or stops. Both pre-V1 continuations (the evidence-only run and the limited V1-only review) are named, bounded and recorded, and neither clears the defect nor authorizes ordinary downstream work. Contract-only repair is a new review state even when no code work is pulled (subject rule above; closure-verification.md). The run proceeds to Vector 1 only after this gate.
- **Phase 0 fail-closed producer gate.** The gate opens only with the pinned producer's sealed evidence, listed with the manifest: capture manifest sha256, canonical `registry_hash`, the run manifest (`claim-run-manifest/2` for sliced runs, never a downgraded `/1`), and the `gate-check` report at exit 0 **with both permission flags true** (plus the declared labeling mode and the `--require-sliced` invocation when sliced), together with the 0.3a `census` artifact hash and a passing `census check`. A pin mismatch, exit 2 (missing/wrong pinned dependency), any failed producer step, a missing gate permission, or a claims/coverage projection mismatch **stops Phase 0** — no run-authored compiler, no hand-built registry, no relaxed gate, no silent substitution of an older head.

## Output

The run manifest (also written to the notebook page, see libs/pi-driver/references/notebook-plan-contract.md):

```text
run: owner/repo pr# — review state <n>
subject_path: <pulled tree dir>   # sandbox or plain worktree — the tree under review
subject_oid: <git HEAD of the pulled tree at Phase 0>   # whatever the pull has; the version reviewed
base_oid: <PR base>   remote_head_oid: <gh-reported PR head at intake — informational>
vectors: [..]  groups: {flash, code-review}
draft_comment, pauses
changed_files: [...]
contract_ref: contract-<owner>-<pr>-s<n>   # notebook page (pi); disk path in fallback runs
contract_sources: [{class, pointer, path/section, role, blob_subject, blob_base, capture_sha256, capture_byte_length, hash, version_ref}]   # captured claim sources: PR body/issue version pins + explicitly designated in-diff sources; byte identity (capture) and repo blob OID are distinct dual pins (§0.2)
toolchain: {producer: {version: 0.3.0, artifact_sha256, describe_sha256, tool_manifest_ref}, gate: {version: 0.2.0, artifact_sha256, report_ref, exit, permission: {finalized_unclaimed, complete_registry_claims}}, census: {version: 0.1.0, artifact_sha256}}   # engine's own pinned copies (D4); subject-tree executables never invoked
claims: {registry_ref, registry_hash, manifest_ref, manifest_schema: claim-run-manifest/1 | 2, labeling_mode: full | sliced, labeling_ref, validation_report_ref, gate_permission: {finalized_unclaimed, complete_registry_claims}}   # canonical producer registry; claims/coverage pages are projections with identical IDs/counts/registry_hash; window/slice IDs never become claim IDs
source_consistency: {status: clean | recorded-inconsistency | provisional-repair-required, records_ref, evidence_only_v1: none | <operator ref + scope>}   # early pass outcome; provisional repair defaults to pause before Vector 1 (§0.4)
review_basis: {value: ready | limited-only | blocked | unknown, repair_required, blockers, allowed_next_scope, operator_disposition_ref}   # recorded after Vector 1 at the gate (conformance-pass.md), bound to the state's source pins + canonical registry hash + gate permission + census hash + coverage pins
coverage: {version, owner: v1, status, summary_ref: coverage-<owner>-<pr>-s<n>, ledger_refs: [coverage-<owner>-<pr>-s<n>-p<k>], claims_ref/hash (canonical-registry projection), census: {ref, census_hash, check_ok}, scope, exclusions: {policy, classes, approvals}, counts_by_state_and_side, completion_flags: {enumeration, accounting, attribution, claim_conformance}, budget, assignment_ref/hash (per-shard digests on the summary page), audit, errors}   # coverage pages are in-notebook only — never authoritative scratch files; retired at state close after durable snapshots (notebook-plan-contract.md, Coverage pages)
notebook (when available): pipeline-frame-<owner>-<pr>-s<n> + contract-<owner>-<pr>-s<n> + claims-<owner>-<pr>-s<n> + coverage-<owner>-<pr>-s<n> (+ ledger shards) + symbol-map-<owner>-<pr>-s<n> + pr-<n>-review   # per review state (pr-<n>-review: per PR); the map is the state's symbol_sweep artifact
lens_matrix: {type: preflight, dead: preflight+v3, read: v2+v3, name: v3, blast: preflight+v2, quality: v3}   # see hygiene-lens.md + blast-lens.md + quality-lens.md
symbol_sweep: <artifact ref — state's symbol map page/file (symbol-map-<owner>-<pr>-s<n> | scratch path); mode: chhound-rail | rg>   # preflight symbol map, recipe in chhound-driver.md (Symbol sweep); reused by V2/V3/yagni + the comment render
symbol_sweep_symbols: [..]   # optional: explicit identifiers the operator adds to the extracted sweep set
research: {mode: chhound-rail | direct-tree, ch_prefix: <registered chh_* prefix | none>, excluded: [<other live chh_* prefixes>], v2_protocol: code-research-if-ready, v3_protocol: search-extensive-if-ready, shadow: off}   # protocols in implementation-pass.md + debt-pass.md; shadow on only by explicit operator choice
cure_light_source_head_oid: <cure-light source HEAD at intake>   # review provenance, frozen once (see evidence-format.md)
```

The provenance field `cure_light_source_head_oid` is captured **once, at intake**, from the cure-light source checkout (`git -C <cure-light clone> rev-parse HEAD`). It is the "version at the time of reviewing": the single review comment composes its attribution footer from this manifest value alone, never re-derived per vector (see evidence-format.md, External routing).

Every lens in the matrix must have ≥1 owning pass before Phase 0 proceeds — a
lens without an owner is a frame error, not a "nothing found" default.
