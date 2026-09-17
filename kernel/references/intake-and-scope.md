# intake-and-scope.md — Phase 0: pull the subject, build the contract

Phase 0 runs once per **review state**. Its output is the **run manifest** — the single source of truth for every subsequent vector and the closure loop.

## The subject rule

cure-light reviews the tree it **pulls**, not the remote tip. Whatever SHA the pulled tree has at pull time is the version under review (reviewing the latest is desired, not a risk). The tree is stable for the whole state — nothing mutates it mid-run; a deliberate re-pull at an operator gate starts a **new review state** and updates the tree in place to the new head at that boundary (or pulls fresh when the tree is gone/broken, §0.1). Evidence is anchored to the subject; a state's findings never mix trees.

## 0.1 Pull the subject (preflight, ground truth)

**Subject-first.** Until the subject is pulled, nothing in the target repo's local checkouts is read or used for orientation — per review state (a deliberate re-pull starts a new state under the same rule). Pre-pull access is remote-only (`gh repo view` / `gh pr view` / `gh pr diff --name-only`) plus presence probes (pi-chhound install checks; the operator's `/ch-status` report at the frame gate confirms the rail); the only pre-pull local git command is the cure-light source provenance capture (§Output below). The pulled subject is the first tree cure-light reads for context or evidence.

At Phase 0:

- [ ] `gh auth status` — logged in, `repo` scope.
- [ ] `gh repo view <owner>/<repo>` reachable.
- [ ] `gh pr view <pr> --json headRefOid,baseRefOid,state,title` — PR exists and is OPEN; capture `baseRefOid` + the remote `headRefOid` as **informational context** (what gh reports now; NOT the subject).
- [ ] Pull the subject tree:
      - **re-pull, tree exists** (a new review state for a PR already pulled at `subject_path`) → update it **in place**: fetch the new head into the tree's repo and check it out detached (`git -C <subject_path> fetch …` + `git -C <subject_path> checkout --detach <new head>`). The rail sandbox needs no `/ch` command: its live daemon re-indexes the sandbox automatically and the MCP bridge stays connected. A tree that is gone/broken (or a mechanism change) → pull fresh below.
      - **pi-chhound rail confirmed** (install detected at boot; operator `/ch-status` report at the frame gate) and no subject tree for this PR yet → chunkhound PR sandbox per [chhound-driver.md](chhound-driver.md): the **operator** runs `/chworktree https://github.com/<owner>/<repo>/pull/<n> --dest <unique-dir>` and `/ch-mcp <printed-path> --prefix chh_pr<n>`; the coordinator verifies the `chh_*` tools respond. The sandbox dir is the subject.
      - **else** → plain detached worktree at the PR's current head, sourced as:
            - developer has an existing local clone of the target repo → source from that clone (fetch, then `git worktree add --detach <scratch>/tree <current headRefOid>`). Plumbing only — the clone is the git object source; its working tree is never read as context or evidence.
            - no local clone → clone the target repo into the review scratch dir (`git clone <target-url> <scratch>/tree`), fetch, then `git -C <scratch>/tree checkout --detach <current headRefOid>` — the clone is the subject.
      - `<scratch>` = the review scratch dir (e.g. `/tmp/cure-<owner>-<pr>/`); a fresh plain subject lands at `<scratch>/tree`, an in-place re-pull keeps the existing `subject_path`.
      - If the tree cannot be pulled at all, STOP (no evidence base).
- [ ] **Capture the subject**: `git -C <subject-path> rev-parse HEAD` → manifest `subject_oid`; the tree dir → `subject_path`. If `subject_oid` ≠ the gh-reported `headRefOid`, record both in the manifest — the pulled tree is the subject regardless (informational divergence, not an error). On an in-place re-pull the same `subject_path` gets the new `subject_oid`; the previous state's content stays reachable at its own OID (`git show <old_subject_oid>:<path>`).
- [ ] Complete the deferred requirements rows on the pulled tree (requirements-check.md rows 5/8/9) — the requirements check is complete only after this.
- [ ] (pi) `notebook_index` responds.
- [ ] (pi, optional) chhound index health (`chh_pr<n>_daemon_status`); fallback = bash/rg/grep. A broken index never blocks.

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

Rule: the contract is the PR's own words plus the issue's locked decisions — never the reviewer's paraphrase of intent. Preserve verbatim blocks.

## 0.3 Split vectors into pass slices

Each vector's fleet splits the contract surface. Example split for a model-group/spawn PR:

- conformance: derivation core · persistence/schema guard · spawn/router gate · main-session+TUI · tests
- implementation: sealed concepts the review already established (never open-ended), + **`read` lens and the `blast` judgment rows** (the once-per-state sweep runs in the deterministic preflight)
- debt: pluggability · boundary ownership · versioning/migrations · projections · perf/operability, + **`dead`/`name`/`quality` lens ownership**

Slice granularity is chosen so each child reads a bounded file set + the relevant CONTRACT slice, and returns under a defined evidence budget.

The lens matrix (hygiene-lens.md) is compiled here and validated: every active lens must map to ≥1 owner. Deterministic preflight (strict tsc / lint) is the `type` sweep and `dead` accelerant; it also produces the state's once-per-state `symbol_sweep` symbol map (recipe: chhound-driver.md, Symbol sweep) — consumed by the V2 splits for the `sweep` row, seeded into V3 debt and the yagni pass, and rendered as the comment's `Symbol impact`.

## 0.4 Operator gates

- **Plan gate (pre-pull).** Before Phase 0 mutates anything external, surface the compiled plan for confirmation: subject mechanism (chhound sandbox | plain worktree) and planned location, vectors, splits, groups, gates, output policy. The planned research mode (chhound-rail when the sandbox rail is planned, else direct-tree — pipeline-model.md) is part of the plan. The frame carries **no tree fields yet** — `subject_path` / `subject_oid` cannot exist before the pull (subject-first, §0.1).
- **Phase 0 gate (post-pull).** Surface the manifest with the recorded reality: actual `subject_path` / `subject_oid`, `base_oid`, changed-file list from the pulled tree, deferred requirements-row outcomes, fallback notes — a chhound-rail fallback (rail confirmed but sandbox pull/connect failed) also flips `research.mode` to `direct-tree` and `ch_prefix` to `none` (pipeline-model.md), so children render Variant B, never a rail variant whose tools are not connected. The run proceeds to Vector 1 only after this gate.

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
notebook (when available): pipeline-frame-<owner>-<pr>-s<n> + contract-<owner>-<pr>-s<n> + symbol-map-<owner>-<pr>-s<n> + pr-<n>-review   # per review state (pr-<n>-review: per PR); the map is the state's symbol_sweep artifact
lens_matrix: {type: preflight, dead: preflight+v3, read: v2+v3, name: v3, blast: preflight+v2, quality: v3}   # see hygiene-lens.md + blast-lens.md + quality-lens.md
symbol_sweep: <artifact ref — state's symbol map page/file (symbol-map-<owner>-<pr>-s<n> | scratch path); mode: chhound-rail | rg>   # preflight symbol map, recipe in chhound-driver.md (Symbol sweep); reused by V2/V3/yagni + the comment render
symbol_sweep_symbols: [..]   # optional: explicit identifiers the operator adds to the extracted sweep set
research: {mode: chhound-rail | direct-tree, ch_prefix: <chh_pr<n> | none>, excluded: [<other live chh_* prefixes>], v2_protocol: code-research-if-ready, v3_protocol: search-extensive-if-ready, shadow: off}   # protocols in implementation-pass.md + debt-pass.md; shadow on only by explicit operator choice
cure_light_source_head_oid: <cure-light source HEAD at intake>   # review provenance, frozen once (see evidence-format.md)
```

The provenance field `cure_light_source_head_oid` is captured **once, at intake**, from the cure-light source checkout (`git -C <cure-light clone> rev-parse HEAD`). It is the "version at the time of reviewing": the single review comment composes its attribution footer from this manifest value alone, never re-derived per vector (see evidence-format.md, External routing).

Every lens in the matrix must have ≥1 owning pass before Phase 0 proceeds — a
lens without an owner is a frame error, not a "nothing found" default.
