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

## 0.2 Capture sources and draft claims

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

A pointer in the PR body, linked issue, or a locked decision may **explicitly designate** an in-diff spec/design file or package (an openspec-style change package, a changed design/spec doc) as a claim source. The explicit pointer is the trust stamp: repository convention (openspec layout, ADR folder, delta conventions) may **interpret** a designated package — which of its files are normative vs advisory, which clauses are the operative delta vs the retained baseline, how its roles fit — but convention alone never confers authority, and an unpointed spec-looking file, changed README, incidental design paragraph or test snapshot is ordinary changed documentation: evidence or context, never a claim source. Record per source block: source class, the designating pointer, the selection/interpretation rule plus any base-side policy citation, path/section, normative vs advisory status, and explicit precedence (if any). The current source-format policy remains **Markdown** for designated claim sources; a designated non-Markdown source is captured as **context with a stated limitation** (never a claim source). Source-format expansion is an explicit checkpoint, not a side effect of replacing the old parser. A pointed resource that cannot be captured and pinned is likewise **context with a stated limitation**, never adjudicated as if read. When required designation or orientation is missing, record a `repair_required` record with `required: true` (the P0.2 `source_consistency` outcome stays clean) and record the affected changed units for V1 attribution against the captured contract pending repair; Phase 0 never finalizes UNCLAIMED. Never a reviewer-invented claim.

### P0.1 Immutable source capture

Capture the authorized sources verbatim, with exact-byte sha256 refs and version identity. Record `subject_oid` / `base_oid`, actual repo blob OIDs for selected in-diff sources (base blobs where delta interpretation needs them), source roles/designating pointers/selection rules, and timestamped PR body/issue snapshots. Source content comes from `git show <subject_oid>:<path>`, never a live edited checkout or the remote tip. A changed source version mid-state quarantines stale results and opens a new state at the operator gate — no mixed-source findings. The verbatim contract and capture refs remain authoritative; a drafted claim statement is not a replacement source.

### P0.2 Claims pass (`#fast`)

Read all captured, designated sources before inspecting delivery. Produce `claims-draft/3`: `sources`, `claims`, `nonclaims`, `conflicts`, `notes`, and structured `missing_source_candidates`. Each claim carries a run-scoped `id`, `statement`, `source_ref`, verbatim `quote`, and `also_in` source refs. Claims are promises or acceptance requirements: include a stated "Fixes X"; separate background defects, evidence and advisory discussion into nonclaims/notes, and never classify the same clause as both claim and nonclaim.

The draft absorbs the bounded **within-source and cross-source consistency pass**: compare material purpose/scope/behavior declarations, not every phrasing difference. Preserve conflicting quotes, offsets/source hashes, affected draft IDs and materiality reasoning in the source-consistency records. A material unresolved contradiction without explicit/locked precedence records a `repair_required` record (`required: true`, with its consistency witnesses) and defaults to pause before V1. Only an explicit operator disposition in `repair_required.continuation` — a named, bounded `evidence-only-v1` or `limited-v1-only` mode with scope and operator ref — may proceed through that pause; it neither clears the defect nor authorizes ordinary downstream work. Non-material wording inconsistencies are recorded without pausing. Clarification or repaired sources open a new review state. V1 audits the draft against the captured sources and dispositions these records (accept, or dispute with a witness); it re-opens the bounded pass only on a missing/uncaptured designated source, a quote/source-ref fidelity failure, a disputed/unsupported record, or a material contradiction the audit itself surfaces (conformance-pass.md). The final `review_basis` is computed after V1, not here.

Missing-source candidates name the resource, affected draft IDs, the reference quote and why it matters. They do not grant source authority or silently expand the contract; capture or record the limitation at the operator gate. Missing designation/orientation records a `repair_required` record with `required: true` (the P0.2 `source_consistency` outcome stays clean). Draft IDs are run-scoped handles, never canonical semantic identities. Preserve worker drafts and attempts; V1 validates and freezes claims against the captured sources before adjudication. Cross-run label/count differences are diagnostic only until source and instruction provenance are reconciled.

## 0.3 Chunk units, propose links, check the sweep

```text
P0.1 source capture (verbatim bytes + sha256 refs)
  → P0.2 claims pass (#fast; claims-draft/3 + source-consistency)
  → P0.3 shipped chunker (units manifest + whole-unit payloads)
  → P0.4 join pass (#fast; compact per-box join JSONL attempt — row shape P0.4)
  → P0.5 coordinator gate (counts, types, witnesses, budgets, complete sweep)
  → join-draft/1 + candidate-unclaimed[]
  → capacity-bounded V1 split → operator Phase-0 gate
```

### P0.3 Shipped chunker

Run the engine's [chunker](chunker.md), `kernel/tools/chunker.mjs`, over the state's two-dot `base_oid..subject_oid` diff. The compiled frame records its path, exact-byte sha256 and recipe; its identity rides `cure_light_source_head_oid`. The tool is shipped by cure-light, not supplied by the subject tree. It uses fixed windows at logical boundaries: target 4 KiB, ceiling 6 KiB; prefer file-end → hunk-end → block-end → line-end, never mid-line. The manifest and unit payloads are the inventory for the join and V1 accounting. Context and repeated hunk ranges are not unique changed-line counts; see the chunker contract and its explicit limitations. A missing or unrepresentable changed surface cannot quietly disappear into a completeness claim.

### P0.4 Join pass (`#fast`)

Pack boxes by **input length only**: instructions + the full claim-ID/statement list + whole units in manifest order until the next unit no longer fits. Charge fixed input first; never trim the claims, split a unit across children, or add a unit-count cap. If fixed input or the next whole unit cannot fit an empty box, pause for a recorded budget decision. The input ceiling remains an operator-approved pilot value. There is **no output reservation in packing**; actual output is monitored separately.

Each child reads its complete claim list and assigned unit files and is the sole writer of one exact output path. Return compact JSONL: one row per assigned unit in order, including empty results; within `links`, one entry per `(unit_id, claim_id)`, no per-unit link cap. Link fields are `claim_id`, `closeness` (high/medium/low), `role_hint` (implements/tests/necessary-support/removes/changes), and a nonempty, single-line verbatim witness from that unit. The pilot witness limit is 160 characters including the diff marker. Outer fields are `unit_id`, `links`, `unresolved` (null or a reason). Links mean "look here", never "this works". Appending is optional; JSONL on disk is mandatory. Verify the exact output path and return only a compact summary/path, not the rows in the coordinator's context.

### P0.5 Coordinator gate

The gate is coordinator behavior, **not a shipped gate tool**. Check the expected path and exact assigned-unit sweep; strict row types and required fields; one row per unit and one link per unit/claim pair; valid IDs and enums; witness length, single-line form and containment in that unit's exact bytes; and recorded input/output budgets. Check zero-link units, zero-link claims and unresolved/hard cases separately. A missing/truncated/invalid row is never an empty match. Retain attempts, retry/re-split within the approved policy, and disclose unresolved residue when recovery is exhausted — never reuse a stale successful merge. The retry/re-split policy and production input ceiling remain pilot checkpoints.

Merge validated records into `join-draft/1`; zero-link, decidable units are only `candidate-unclaimed[]`. P0.5 validates mechanics and sweep completeness, not claim correctness, complete source interpretation or final negative attribution. V1 validates/freezes claims, judges delivery and alone finalizes UNCLAIMED. Suite-level claims without a single-unit witness and the real missing-source/designation cases remain explicit hard cases, never guessed links or invented claims.

### Capacity-bounded vector split compile

Each vector's fleet splits the contract surface, capacity-bounded within the approved budget. Example split for a model-group/spawn PR:

- conformance: contract surfaces (derivation core · persistence/schema guard · spawn/router gate · main-session+TUI · tests), each compiled into bounded claim/range shards — one verdict owner per claim, one accounting owner per unit — plus residual attribution shards for changed units with no candidate claim — candidate-unclaimed entries are leads for V1, never final negatives (work packaging only, never invented contracts)
- implementation: sealed concepts the review already established (never open-ended), + **`read` lens and the `blast` judgment rows** (the once-per-state sweep runs in the deterministic preflight)
- debt: pluggability · boundary ownership · versioning/migrations · projections · perf/operability, + **`dead`/`name`/`quality` lens ownership**

Slice granularity is chosen so each child reads a bounded file set + the relevant contract slice + its assigned artifact refs and V1 coverage shard pages, and returns under a defined evidence budget.

The split compile asserts **Vector 1 coverage** — a verdict owner for every captured claim, an accounting owner for every eligible (non-excluded) changed unit — distinct from the lens assertion below. The lens matrix (hygiene-lens.md) is compiled here and validated: every active lens must map to ≥1 owner. Deterministic preflight (strict tsc / lint) is the `type` sweep and `dead` accelerant; it also produces the state's once-per-state `symbol_sweep` symbol map (recipe: chhound-driver.md, Symbol sweep) — consumed by the V2 splits for the `sweep` row, seeded into V3 debt and the yagni pass, and rendered as the comment's `Symbol impact`.

## 0.4 Operator gates

- **Plan gate (pre-pull).** Before Phase 0 mutates anything external, surface the compiled plan for confirmation: subject mechanism (chhound sandbox | plain worktree) and planned location, vectors, splits, groups, gates, output policy. The planned research mode (chhound-rail when the sandbox rail is planned, else direct-tree — pipeline-model.md) is part of the plan. The frame carries **no tree fields yet** — `subject_path` / `subject_oid` cannot exist before the pull (subject-first, §0.1).
- **Phase 0 gate (post-pull).** One gate with three sub-checklists:
      - **Artifact validity** — the written verbatim `contract-<owner>-<pr>-s<n>` page (or the prescribed `CONTRACT.md` disk fallback) exists at `contract_ref`, is readable and matches it; the source capture identities; the shipped chunker path/sha256/recipe bound to `cure_light_source_head_oid`; the state's claims-draft, units-manifest and join-draft refs/hashes. Check P0.5 evidence against expected assignments and disclose retry/resplit failures, incomplete sources and hard cases. Missing or stale artifacts never authorize complete coverage; pause or record the operator-approved limited scope. No installed claim plugin, canonical claim-ID permission or census gate is required. The gate does not finalize UNCLAIMED or establish `review_basis: ready`; those remain V1 responsibilities.
      - **Plan reality** — surface the manifest with the recorded reality: actual `subject_path` / `subject_oid`, `base_oid`, changed-file list from the pulled tree, unit/file/line-split counts, P0.5 expected/received rows and link counts, zero-link claims, candidate-unclaimed units and unresolved hard cases and the exclusion policy (evidence-linked classes — a path suffix alone is never sufficient), coverage-page location and budgets it approves, deferred requirements-row outcomes, fallback notes — a chhound-rail fallback (rail confirmed but sandbox pull/connect failed) also flips `research.mode` to `direct-tree` and `ch_prefix` to `none` (pipeline-model.md), so children render Variant B, never a rail variant whose tools are not connected.
      - **Repair + continuation** — the P0.2 `source_consistency` outcome (clean or recorded non-material inconsistency) and the independent `repair_required` record (`required`, `records`, `continuation`); missing designation/orientation is a clean-consistency + `required: true` case. A `required: true` record defaults the run to **pause before Vector 1**: the operator requests author clarification/repair, or records an explicit disposition in `repair_required.continuation` — a named, bounded `evidence-only-v1` or `limited-v1-only` mode with scope and operator ref (recorded scope/rationale/state) — that does not clear the defect or authorize ordinary downstream work. Thinness is judged across all explicitly designated, capturable sources — not PR-body length: a terse body with an accurate pointer to a complete designated package can pass; reviewer-invented claims are never an option. The repair-pause default applies to any `repair_required` defect (missing designation/orientation included), not just contradictions: the operator requests author repair, runs an explicitly limited V1-only review, or stops. Both pre-V1 continuations (the evidence-only run and the limited V1-only review) are named, bounded and recorded, and neither clears the defect nor authorizes ordinary downstream work. Contract-only repair is a new review state even when no code work is pulled (subject rule above; closure-verification.md). The run proceeds to Vector 1 only after this gate.

## Output

The run manifest (also written to the notebook page, see libs/pi-driver/references/notebook-plan-contract.md):

```text
run: owner/repo pr# — review state <n>
subject_path: <pulled tree dir>   # sandbox or plain worktree — the tree under review
subject_oid: <git HEAD of the pulled tree at Phase 0>   # whatever the pull has; the version reviewed
base_oid: <PR base>   remote_head_oid: <gh-reported PR head at intake — informational>
vectors: [..]  groups: {claims: fast, join: fast, conformance: flash, implementation: code-review, debt: code-review}
draft_comment, pauses
changed_files: [...]
contract_ref: contract-<owner>-<pr>-s<n>   # notebook page (pi); disk path in fallback runs
contract_sources: [{class, pointer, path/section, role, blob_subject, blob_base, capture_sha256, capture_byte_length, hash, version_ref}]   # source designation + captured bytes/version refs + actual repo blob OIDs where applicable; no plugin synthetic blob identity
chunker: {path: kernel/tools/chunker.mjs, sha256, recipe: {target_bytes: 4096, ceiling_bytes: 6144, context: 3, block_preference: true}}   # shipped engine tool; path + exact-byte sha256 + recipe bound to cure_light_source_head_oid
claims_draft: {ref, sha256, schema_version: claims-draft/3}   # run-scoped proposal; V1 validates/freezes against captured sources
units_manifest: {ref, sha256, schema_version: code-units-sim/2}   # current emitted schema; inventory order + payload refs, not unique changed-line counts
join_draft: {ref, sha256, schema_version: join-draft/1}   # P0.4 leads merged only after P0.5; candidate-unclaimed is not a final accounting state
source_consistency: {status: clean | recorded-inconsistency, records_ref}   # P0.2 comparison outcome only; missing designation/orientation records repair_required without an inconsistency
repair_required: {required, records: [{reason, affected_scope, evidence_refs[]}], continuation: {mode: none | pause | evidence-only-v1 | limited-v1-only, scope, operator_disposition_ref}}   # independent Phase-0 record; required=true defaults to pause before Vector 1; only an explicit operator disposition sets evidence-only/limited modes (scope + ref), and neither clears the defect nor authorizes ordinary downstream work
review_basis: {value: ready | limited-only | blocked | unknown, repair_required: {required, records, continuation}, blockers, allowed_next_scope, operator_disposition_ref}   # recorded after V1; repair_required reuses the Phase-0 record shape and identity (same frame page), finalized here, never recomputed; bound to source versions, Phase-0 artifact refs/hashes, V1 frozen claims + coverage evidence
coverage: {version, owner: v1, status, summary_ref: coverage-<owner>-<pr>-s<n>, ledger_refs: [coverage-<owner>-<pr>-s<n>-p<k>], claims_ref/hash, scope, exclusions: {policy, classes, approvals}, counts_by_state_and_side, completion_flags: {enumeration, accounting, attribution, claim_conformance}, budget, assignment_ref/hash, audit, errors}   # V1 frozen claim directory + accounting over units_manifest; notebook pages remain authoritative for V1 states
notebook (when available): pipeline-frame-<owner>-<pr>-s<n> + contract-<owner>-<pr>-s<n> + claims-<owner>-<pr>-s<n> + coverage-<owner>-<pr>-s<n> (+ ledger shards) + symbol-map-<owner>-<pr>-s<n> + pr-<n>-review   # per review state (pr-<n>-review: per PR); the map is the state's symbol_sweep artifact
lens_matrix: {type: preflight, dead: preflight+v3, read: v2+v3, name: v3, blast: preflight+v2, quality: v3}   # see hygiene-lens.md + blast-lens.md + quality-lens.md
symbol_sweep: <artifact ref — state's symbol map page/file (symbol-map-<owner>-<pr>-s<n> | scratch path); mode: chhound-rail | rg>   # preflight symbol map, recipe in chhound-driver.md (Symbol sweep); reused by V2/V3/yagni + the comment render
symbol_sweep_symbols: [..]   # optional: explicit identifiers the operator adds to the extracted sweep set
research: {mode: chhound-rail | direct-tree, ch_prefix: <registered chh_* prefix | none>, excluded: [<other live chh_* prefixes>], v2_protocol: code-research-if-ready, v3_protocol: search-extensive-if-ready, shadow: off}   # protocols in implementation-pass.md + debt-pass.md; shadow on only by explicit operator choice
cure_light_source_head_oid: <cure-light source HEAD at intake>   # review provenance, frozen once (see evidence-format.md)
```

**Pilot checkpoints.** The input ceiling and retry/re-split policy, suite-level claim handling, possible tightening of `medium`, and the detailed V1 freeze/return contract require operator review. The current artifact examples do not define a populated conflict-record schema or the candidate-unclaimed element encoding; neither is silently settled by this manifest. A referenced but uncaptured defining source requires an explicit capture-or-limitation decision.

The provenance field `cure_light_source_head_oid` is captured **once, at intake**, from the cure-light source checkout (`git -C <cure-light clone> rev-parse HEAD`). It is the "version at the time of reviewing": the single review comment composes its attribution footer from this manifest value alone, never re-derived per vector (see evidence-format.md, External routing).

Every lens in the matrix must have ≥1 owning pass before Phase 0 proceeds — a
lens without an owner is a frame error, not a "nothing found" default.
