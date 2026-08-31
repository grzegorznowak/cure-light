---
name: cure-light
description: Run a structured three-vector pull-request review — contract-vs-code conformance, implementation bugs, code debt — with a pinned-commit snapshot, spawned fleet passes, and a closure-verification loop. Use when asked to review a GitHub pull request, assess a branch diff, or coordinate a multi-agent code review. Requires git, gh, optional child-agent spawning, and (on pi) the session notebook.
---

# cure-light — PR review pipeline

A **diagnostic review, not a fixer.** cure-light reviews a PR against its own stated contract and the surrounding codebase; it does not modify code. Findings surface as a **single review comment**, drafted only through operator-gated finalization.

Read these references completely before establishing a process:

1. [references/pipeline-model.md](references/pipeline-model.md) — the 3-vector model, phases, gates
2. [references/intake-and-scope.md](references/intake-and-scope.md) — Phase 0 pin + contract
3. [references/conformance-pass.md](references/conformance-pass.md) — Vector 1
4. [references/implementation-pass.md](references/implementation-pass.md) — Vector 2
5. [references/debt-pass.md](references/debt-pass.md) — Vector 3
6. [references/closure-verification.md](references/closure-verification.md) — the re-review loop
7. [references/hygiene-lens.md](references/hygiene-lens.md) — the lens dimension: code-hygiene family, deterministic preflight, lens trail
8. [references/yagni-pass.md](references/yagni-pass.md) — the optional size/YAGNI pass (fresh-context, post-handoff)
9. [references/quality-lens.md](references/quality-lens.md) — the `quality` lens (V3-owned: maintainable shape, suite strength, consistency)
10. [references/evidence-format.md](references/evidence-format.md) — finding schema, severity, origin

Read [libs/pi-driver/SKILL.md](../../libs/pi-driver/SKILL.md) only if this runtime provides the pi session notebook; its references define the requirements check and the notebook plan contract.

## Initialization contract

### 0. Run the quick requirements check (pi runtimes)

If the pi notebook driver applies, run it first per `libs/pi-driver/references/requirements-check.md`. If any hard requirement is missing, stop before fleet cost or state the fallback. Never start a fleet on an unverified subject.

### 1. Ask the intake fields once

Collect exactly once; never infer defaults for what only the operator can supply:

| Field | Meaning | Example |
|---|---|---|
| `owner/repo` | target repository | `agenticoding/pi-agenticoding` |
| `pr` | pull request number | `27` |
| `vectors` | which vectors to run; yagni optional | `[conformance, implementation, debt]` or `+ yagni` |
| `draft_comment` | whether the pipeline may draft the single aggregated review comment for operator approval (alias: `auto_draft`) | `false` |
| `pauses` | operator checkpoints (default: pause after each vector) | `[per_vector]` |
| `checkout_policy` | require the local checkout to equal PR head | `require_pr_head` |

Ask once. If an operator already answered via a filled `KICKOFF.md`, honor it verbatim.

### 2. Freeze the review frame

Pin the subject BEFORE any analysis: PR head OID, base OID, and the changed-file list captured at intake. Every fleet child receives the same pinned manifest. Reject mixed-SHA evidence. A PR head move mid-review starts a new review state, linked by `git diff old_head..new_head` and handled by the closure loop — never re-run in place.

### 3. Compile the process

From the intake fields, compile: the vector set and their fleet groups, the phase order and operator gates, the notebook pages (run frame + findings), and the output policy (what may be drafted, what waits). Surface the compiled frame to the operator for confirmation before Phase 0.

## Phase order & gates

```text
Intake → Requirements check → [operator gate: frame]
  → Phase 0 pin+contract → [gate]
  → Vector 1 conformance (flash) → [gate]
  → Vector 2 implementation (code-review) → [gate]
  → Vector 3 debt (code-review) → [gate]
  → Optional yagni pass (code-review; size/YAGNI — operator-enabled, fresh-context post-handoff) → [gate]
  → Output (operator-gated drafts) → [closure loop on new head]
```

Each vector is a **fleet pass** with a defined split, per-child prompt contract (assets/child-pass-prompt-template.md), evidence return format (evidence-format.md), and aggregation rule. Truncated or timed-out child output is `inconclusive`, never a pass.

## Closure verification loop

When the operator says the implementer "worked on the review", do NOT re-run the whole pipeline. Fetch the new head, verify the checkout advanced, diff the finding-touched paths, and classify each finding:

- `verified-fixed` — code + test evidence at old/new lines
- `re-classified` — category/claim changed
- `deferred-decision` — acknowledged but knowingly unfixed (never presented as fixed)
- `closed-by-operator` — operator suppressed it (e.g. "don't re-raise"); auditable, re-openable on new evidence
- `re-opened` — prior proof no longer holds

Publish a closure table. See closure-verification.md.

## Operating rules (short version)

- **Review the pinned commit, not the branch tip.** Snapshot everything at intake.
- **Findings need file:line evidence and a concrete failure mode.** Opinion without evidence does not enter the report.
- **Pre-existing vs PR-introduced is a first-class classification**, decided by base-diff, not vibes.
- **Never draft external artifacts automatically.** The single review comment is operator-gated; the `before_post` gate is mandatory whenever drafting is enabled.
- **Deferred is not closed.** Record it in the decisions page with rationale.
- **Fleets are budgeted.** Cap children, timeouts, output; serialize notebook writes via the coordinator.
- **Lens coverage is a preflight assertion.** The run frame must map every active lens to an owning pass (lens matrix, see hygiene-lens.md); a lens without an owner blocks the run.
- **Optional passes are opt-in.** The yagni pass runs only when the operator enables it; a skipped pass deactivates its lens (matrix shows `off`, exempt from the coverage assertion).
