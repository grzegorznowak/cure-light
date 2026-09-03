# intake-and-scope.md — Phase 0: pull the subject, build the contract

Phase 0 runs once per **review state**. Its output is the **run manifest** — the single source of truth for every subsequent vector and the closure loop.

## The subject rule

cure-light reviews the tree it **pulls**, not the remote tip. Whatever SHA the pulled tree has at pull time is the version under review (reviewing the latest is desired, not a risk). The tree is stable for the whole state — nothing mutates it mid-run — and a deliberate re-pull at an operator gate starts a **new review state**. Evidence is anchored to the subject; a state's findings never mix trees.

## 0.1 Pull the subject (preflight, ground truth)

**Subject-first.** Until the subject is pulled, nothing in the target repo's local checkouts is read or used for orientation — per review state (a deliberate re-pull starts a new state under the same rule). Pre-pull access is remote-only (`gh repo view` / `gh pr view` / `gh pr diff --name-only`) plus presence probes (`/ch-status`); the only pre-pull local git command is the cure-light source provenance capture (§Output below). The pulled subject is the first tree touched.

At Phase 0:

- [ ] `gh auth status` — logged in, `repo` scope.
- [ ] `gh repo view <owner>/<repo>` reachable.
- [ ] `gh pr view <pr> --json headRefOid,baseRefOid,state,title` — PR exists and is OPEN; capture `baseRefOid` + the remote `headRefOid` as **informational context** (what gh reports now; NOT the subject).
- [ ] Pull the subject tree:
      - **pi-chhound present** (`/ch-status` responds) → chunkhound PR sandbox per [chhound-driver.md](chhound-driver.md): `/chworktree https://github.com/<owner>/<repo>/pull/<n> --dest <unique-dir>`, then `/ch-mcp <printed-path> --prefix chh_pr<n>`. The sandbox dir is the subject.
      - **else** → plain detached worktree at the PR's current head. Source: the developer's existing local clone of the target repo when one exists — used as the git object source only (fetch, then `git worktree add --detach <scratch>/tree <current headRefOid>` from that clone); its working tree is never read as context or evidence. Otherwise clone the target repo into the review scratch dir at Phase 0 and worktree-add from that clone. `<scratch>` = the review scratch dir (e.g. `/tmp/cure-<owner>-<pr>/`), the subject at `<scratch>/tree`.
      - If the tree cannot be pulled at all, STOP (no evidence base).
- [ ] **Capture the subject**: `git -C <subject-path> rev-parse HEAD` → manifest `subject_oid`; the tree dir → `subject_path`. If `subject_oid` ≠ the gh-reported `headRefOid`, record both in the manifest — the pulled tree is the subject regardless (informational divergence, not an error).
- [ ] Complete the deferred requirements rows on the pulled tree (requirements-check.md rows 5/8/9) — the requirements check is complete only after this.
- [ ] (pi) `notebook_index` responds.
- [ ] (pi, optional) chhound index health (`chh_pr<n>_daemon_status`); fallback = bash/rg/grep. A broken index never blocks.

If any hard requirement fails: state the fallback (git/rg instead of chhound; plain worktree instead of sandbox; inherit-parent instead of fleet groups) or STOP before fleet cost.

## 0.2 Capture the contract

The contract lives in the **run store**: when the runtime's requirements check
confirms the notebook, Phase 0 writes it to the notebook page
`contract-<owner>-<pr>` (one per review state, named like the frame page of
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
- implementation: sealed concepts the review already established (never open-ended), + **`read` lens ownership**
- debt: pluggability · boundary ownership · versioning/migrations · projections · perf/operability, + **`dead`/`name`/`quality` lens ownership**

Slice granularity is chosen so each child reads a bounded file set + the relevant CONTRACT slice, and returns under a defined evidence budget.

The lens matrix (hygiene-lens.md) is compiled here and validated: every active lens must map to ≥1 owner. Deterministic preflight (strict tsc / lint) is scheduled as the cheap sweep for the `type` lens and accelerant for `dead`.

## 0.4 Operator gates

- **Plan gate (pre-pull).** Before Phase 0 mutates anything external, surface the compiled plan for confirmation: subject mechanism (chhound sandbox | plain worktree) and planned location, vectors, splits, groups, gates, output policy. The frame carries **no tree fields yet** — `subject_path` / `subject_oid` cannot exist before the pull (subject-first, §0.1).
- **Phase 0 gate (post-pull).** Surface the manifest with the recorded reality: actual `subject_path` / `subject_oid`, `base_oid`, changed-file list from the pulled tree, deferred requirements-row outcomes, fallback notes. The run proceeds to Vector 1 only after this gate.

## Output

The run manifest (also written to the notebook page, see libs/pi-driver/notebook-plan-contract.md):

```text
run: owner/repo pr# — review state <n>
subject_path: <pulled tree dir>   # sandbox or plain worktree — the tree under review
subject_oid: <git HEAD of the pulled tree at Phase 0>   # whatever the pull has; the version reviewed
base_oid: <PR base>   remote_head_oid: <gh-reported PR head at intake — informational>
vectors: [..]  groups: {flash, code-review}
draft_comment, pauses
changed_files: [...]
contract_ref: contract-<owner>-<pr>   # notebook page (pi); disk path in fallback runs
notebook (when available): pipeline-frame-<owner>-<pr> + contract-<owner>-<pr> + pr-<n>-review   # per review state
lens_matrix: {type: preflight, dead: preflight+v3, read: v2+v3, name: v3, quality: v3}   # see hygiene-lens.md + quality-lens.md
cure_light_source_head_oid: <cure-light source HEAD at intake>   # review provenance, frozen once (see evidence-format.md)
```

The provenance field `cure_light_source_head_oid` is captured **once, at intake**, from the cure-light source checkout (`git -C <cure-light clone> rev-parse HEAD`). It is the "version at the time of reviewing": the single review comment composes its attribution footer from this manifest value alone, never re-derived per vector (see evidence-format.md, External routing).

Every lens in the matrix must have ≥1 owning pass before Phase 0 proceeds — a
lens without an owner is a frame error, not a "nothing found" default.
