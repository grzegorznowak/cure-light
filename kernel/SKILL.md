---
name: cure-light
description: Run a structured three-vector pull-request review — contract-vs-code conformance, implementation bugs, code debt — with a pulled-subject snapshot (one stable tree per review state), spawned fleet passes, and a closure-verification loop. Use when asked to review a GitHub pull request, assess a branch diff, or coordinate a multi-agent code review. Requires git, gh, optional child-agent spawning, and (on pi) the session notebook.
---

# cure-light — PR review pipeline

A **diagnostic review, not a fixer.** cure-light reviews a PR against its own stated contract and the surrounding codebase; it does not modify code. Findings surface as a **single review comment**, drafted only through operator-gated finalization.

Read these references completely before establishing a process:

1. [references/pipeline-model.md](references/pipeline-model.md) — the 3-vector model, phases, gates
2. [references/intake-and-scope.md](references/intake-and-scope.md) — Phase 0 pull subject + contract
3. [references/conformance-pass.md](references/conformance-pass.md) — Vector 1
4. [references/implementation-pass.md](references/implementation-pass.md) — Vector 2
5. [references/debt-pass.md](references/debt-pass.md) — Vector 3
6. [references/closure-verification.md](references/closure-verification.md) — the re-review loop
7. [references/hygiene-lens.md](references/hygiene-lens.md) — the lens dimension: code-hygiene family, deterministic preflight, lens trail
8. [references/blast-lens.md](references/blast-lens.md) — the `blast` lens (V2-owned: data × call-site blast radius, advisory rows vs blocking instances)
9. [references/yagni-pass.md](references/yagni-pass.md) — the optional over-engineering/YAGNI pass (fresh-context, post-handoff)
10. [references/quality-lens.md](references/quality-lens.md) — the `quality` lens (V3-owned: maintainable shape, suite strength, consistency)
11. [references/evidence-format.md](references/evidence-format.md) — finding schema, severity, origin
12. [references/chhound-driver.md](references/chhound-driver.md) — the chunkhound research rail (pi-chhound plugin): sandbox pull, MCP connect, tool names, the symbol-sweep preflight recipe, discovery-only rule

Read [libs/pi-driver/SKILL.md](../libs/pi-driver/SKILL.md) only if this runtime provides the pi session notebook; its references define the requirements check and the notebook plan contract.

## Initialization contract

### 0. Run the quick requirements check (pi runtimes)

If the pi notebook driver applies, run it first per `libs/pi-driver/references/requirements-check.md`. The check splits: pre-pull rows run now; the subject-tree rows defer to the Phase 0 gate once the tree exists — the check is complete only then. The pre-pull rows include pinned toolchain/deps readiness (producer 0.3.0, gate-check 0.2.0, census 0.1.0; python ≥3.11 + uv/venv + the exact tree-sitter pins). If any hard requirement is missing, stop before fleet cost or state the fallback. A missing producer dependency is a fail-loud stop (exit 2), never a fallback registry. Never start a fleet on an unverified subject.

### 1. Ask the intake fields once

Collect exactly once; never infer defaults for what only the operator can supply:

| Field | Meaning | Example |
|---|---|---|
| `owner/repo` | target repository | `agenticoding/pi-agenticoding` |
| `pr` | pull request number | `27` |
| `vectors` | which vectors to run; yagni optional | `[conformance, implementation, debt]` or `+ yagni` |
| `draft_comment` | whether the pipeline may draft the single aggregated review comment for operator approval (alias: `auto_draft`) | `false` |
| `pauses` | operator checkpoints (default: pause after each vector) | `[per_vector]` |

Ask once. If an operator already answered via a filled `KICKOFF.md`, honor it verbatim.

### 2. Pull the review subject

Pull the tree under review BEFORE any analysis or orientation in the target repo's checkouts: a chunkhound PR sandbox when the rail is live (chhound-driver.md §Presence), else a plain detached worktree (intake-and-scope.md §0.1). Until the pull, pre-pull work is remote-only (`gh repo view` / `gh pr view` / `gh pr diff --name-only`) plus presence probes (chhound-driver.md §Presence); the only pre-pull local git command is the cure-light source provenance capture (intake-and-scope.md, §Output). Whatever SHA the pull has is the **subject** — capture it (`subject_oid` / `subject_path`) into the run manifest at Phase 0. Every fleet child of this review state receives the same subject path + OID. The tree is stable for the whole state — nothing mutates it mid-state; only a deliberate re-pull at an operator gate starts a new review state, which obeys the same subject-first rule and updates the tree **in place** at that boundary (intake-and-scope.md §0.1). A tree that is gone or broken is pulled fresh instead.

### 3. Compile the process

From the intake fields, compile: the vector set and their fleet groups, the phase order and operator gates, the **planned subject mechanism** (chhound sandbox | plain worktree) and its planned location, the notebook pages (run frame + findings), and the output policy (what may be drafted, what waits). The research mode (chhound-rail | direct-tree — pipeline-model.md, research accelerator) is compiled from the planned mechanism and frozen with the frame; if the Phase 0 pull falls back from a planned rail to a plain worktree, the mode is re-recorded as `direct-tree` before Vector 1. Surface the compiled frame to the operator for confirmation before Phase 0 — the pre-pull gate approves the plan; the tree's reality (`subject_path` / `subject_oid`) is recorded at the Phase 0 gate. The compiled frame also pins the Phase-0 toolchain: the engine's own `claim-registry` 0.3.0 / `gate-check` 0.2.0 / `census` 0.1.0 copies (version + sha256) and the expected labeling mode (`full` when every source fits ≤16 KiB raw / ≤80 units / ≤64 KiB complete worker input, else `sliced`). Subject-tree executables — including the subject's own `tools/` and demos — are never invoked (D4 invariant); they are reviewed content only.

## Phase order & gates

```text
Intake → Requirements check (pre-pull rows; subject-tree rows defer to Phase 0)
  → [operator gate: frame] — approves the PLAN: subject mechanism (chhound sandbox | plain worktree) + planned location, vectors, gates, output policy; no tree fields yet
  → Phase 0 pull subject + pinned producer (capture → frame / frame-slices → labeling children → proposal-reconcile → assemble → validate → manifest `/2` → gate-check) + source-consistency pass → 0.3a census `run` + `check` → 0.3b split compile → [gate: manifest records reality — subject_path / subject_oid, toolchain pins + gate report/permissions + registry hash + labeling mode, census hash/counts, exclusions/budgets, consistency outcome; provisional repair defaults to pause before V1]
  → Vector 1 conformance (flash; two-ended — claim adjudication + changed-unit accounting) → [gate: review_basis + repair status]
  → Deterministic preflight (type/dead + the state's symbol map)
  → Vector 2 implementation (code-review) → [gate]
  → Vector 3 debt (code-review) → [gate]
  → Optional yagni pass (code-review; over-engineering/YAGNI — operator-enabled, fresh-context post-handoff) → [gate]
  → Output (one operator-gated review comment) → [closure loop on deliberate re-pull]
```

Each vector is a **fleet pass** with a defined split, per-child prompt contract (assets/child-pass-prompt-template.md), evidence return format (evidence-format.md), and aggregation rule. Truncated or timed-out child output is `inconclusive`, never a pass.

## Closure verification loop

When the operator says the implementer "worked on the review" (or re-pulls the PR), do NOT re-run the whole pipeline. The re-pull or contract repair is a new review state: update the subject tree in place to the new head (intake-and-scope.md §0.1; a contract-only repair pulls no new code but recaptures the contract), capture the new subject OID, diff the finding-touched paths last-reviewed-subject → new-subject, and classify each finding:

- `verified-fixed` — code + test evidence at old/new lines
- `re-classified` — category/claim changed
- `deferred-decision` — acknowledged but knowingly unfixed (never presented as fixed)
- `closed-by-operator` — operator suppressed it (e.g. "don't re-raise"); auditable, re-openable on new evidence
- `re-opened` — prior proof no longer holds

Publish a closure table. See closure-verification.md.

## Operating rules (short version)

- **Review the pulled subject tree, not the remote tip.** Whatever SHA the pull has is the version reviewed; capture it at Phase 0 and anchor every finding to it.
- **Subject-first: no orientation before the subject pull.** Until Phase 0 pulls the subject, nothing in the target repo's local checkouts is read or used for orientation — per review state (a deliberate re-pull starts a new state under the same rule). Pre-pull access is remote-only plus presence probes (chhound-driver.md §Presence); the only pre-pull local git command is the cure-light source provenance capture.
- **Findings need file:line evidence and a concrete failure mode.** Opinion without evidence does not enter the report.
- **Coverage accounting is not a findings taxonomy.** Vector 1 keeps `EXPLAINED` / `UNCLAIMED` / `EXCLUDED` / `UNRESOLVED` per-unit states in the in-notebook coverage pages; approved exclusions are evidence-linked policy records, and an unread / truncated / disputed range stays `UNRESOLVED` — disclosed, never silently dropped, relabeled, or inferred from a sibling.
- **Unclaimed delivery is blocking.** A confirmed `unclaimed-delivery` finding is in-scope Vector 1 conformance the owner must address in the PR body — declare/justify the delivered behavior or remove it; never demoted to a follow-up. Severity stays LOW default / MED material / never HIGH from the absence of a declaration alone (evidence-format.md).
- **Sources enter the contract only by explicit designation.** The PR body, linked issue or a locked decision must point at any in-diff spec/design material; repo convention interprets a designated package, never authorizes one (intake-and-scope.md §0.2). A material unresolved source contradiction pauses the run before Vector 1 unless the operator records a named evidence-only V1 authorization — and any other `repair_required` defect (missing designation/orientation) defaults to the same repair pause; never a reviewer-reconciled contract.
- **Continuation is a recorded basis, not an accounting side effect.** After Vector 1, the coordinator records `review_basis` (`ready` / `limited-only` / `blocked` / `unknown`) with any outstanding `repair_required` status; ordinary V2/V3 proceeds only from `ready` with no outstanding repair, and `limited-only` proceeds only through an explicit named scope (conformance-pass.md). A basis disposition never relabels findings, and an accepted finding never establishes readiness.
- **Contract repair is a new state.** A body/issue edit with an unchanged subject OID, or an in-diff source edit with unchanged code blobs, starts a new review state with a recaptured contract; reuse only identity-checked census, re-adjudicate affected claims — never silently inherit findings (closure-verification.md).
- **Partial coverage is stated honestly.** Mechanical enumeration and accounting are always complete for a complete-coverage claim; semantic residue and any accepted partial review are reported with their limits and require explicit operator acceptance at the gate (conformance-pass.md).
- **Closure discloses coverage gaps.** A closure re-review surfaces newly added unexplained ranges outside finding-touched paths, or states plainly that Vector 1 coverage was not re-run — it never claims new full coverage from old dispositions (closure-verification.md).
- **Pre-existing vs PR-introduced is a first-class classification**, decided by base-diff, not vibes — and scope routes the comment: introduced-or-enforced items are addressed, never deferred downstream; out-of-scope items are only recommended or suggested.
- **Never draft external artifacts automatically.** The single review comment is operator-gated; the `before_post` gate is mandatory whenever drafting is enabled.
- **Deferred is not closed.** Record it in the decisions page with rationale.
- **Phase 0 mechanical artifacts are producer-owned and gate-checked.** The claim universe (capture → frame/frame-slices → labeling children → proposal-reconcile → assemble → validate → manifest) comes from the run's pinned `claim-registry` copy; `gate-check` exit 0 with both permission flags is the only authority for a complete registry, and `census run` + `check` supplies the coverage denominator. Zero run-authored compilers, no subject-tree executable, no hand-edited canonical file; a pin mismatch, exit 2 (missing/wrong pinned dependency), failed check, or projection hash mismatch stops Phase 0 (intake-and-scope.md §0.2/§0.3a).
- **Fleets are budgeted.** Cap children, timeouts, output; serialize notebook writes via the coordinator.
- **Lens coverage is a frame assertion.** The run frame must map every active lens to an owning pass (lens matrix, see hygiene-lens.md); a lens without an owner blocks the run.
- **Optional passes are opt-in.** The yagni pass (over-engineering of the claimed delivery — not size accounting, yagni-pass.md) runs only when the operator enables it; a skipped pass deactivates its lens (matrix shows `off`, exempt from the coverage assertion).
- **Subsystem research is mandatory-if-ready on the chhound rail.** When the frame's research mode is `chhound-rail`, Vector 2 runs the code-research protocol (implementation-pass.md) and Vector 3 the search-extensive protocol (debt-pass.md): exact registered tool names are rendered into every child prompt, and a missing RESEARCH TRACE footer makes a split `inconclusive`. In `direct-tree` mode (plain worktree) children never invoke a `chh_*` namespace. Shadow splits are off unless the operator opts in.
