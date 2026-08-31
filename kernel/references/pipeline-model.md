# pipeline-model.md — the three vectors

cure-light reviews a pull request through **three independent vectors**. Each answers a different question; running them in order means later vectors build on a verified substrate.

| Vector | Question | Fleet group | Focus |
|---|---|---|---|
| 1. Conformance | Does the code deliver what the PR *claims* it delivers? | `flash` | PR description + issue + locked decisions → code |
| 2. Implementation | Does the shipped code actually *work* safely? | `code-review` | Sealed concepts / invariants, drilling from established facts |
| 3. Debt | Is the *way* it's built sustainable? | `code-review` | Bigger concepts, future-change cost, not line-by-line |

## Why three vectors

- **Conformance alone is blind to implementation bugs** (spec-satisfying but broken code), and **bugs alone miss contract gaps** (working code that does the wrong thing).
- **Debt is a different granularity.** It looks at boundary ownership, pluggability, versioning, projections, performance — the costs the next feature will pay, not the current failure.

## Sequenced, gated

```text
Intake → Phase 0 → Vector 1 → Vector 2 → Vector 3 → Output (single review comment) → Closure loop (on new head)
```

- Vector 2 runs only when Vector 1 has a clean/accepted disposition (or the operator explicitly allows skipping).
- Vector 3 runs only when the implementation evidence is stable.
- The operator gates between phases. No autonomous new-commit loops.

## Cross-cutting rules

1. **One pinned subject.** All vectors analyze the same head OID (see intake-and-scope.md).
2. **Origin classification is mandatory** (pre-existing vs PR-introduced), decided by base-diff.
3. **Two-axis severity**: impact (HIGH/MED/LOW) × disposition (fix-in-PR / pre-existing-debt / deferred-decision).
4. **Notebook is the shared memory.** The coordinator writes run frame + findings pages; children return compact evidence records, they do not compete for writes.
5. **Inconclusive = no pass.** A child timeout/truncation means the finding is unverified, not accepted.
6. **Fleets are budgeted.** Per-phase child counts, timeouts, output caps, and a cheap re-review path (delta-only) are mandatory.
7. **Review is diagnostic.** cure-light proposes; the operator gates the single external review comment (see evidence-format.md, External routing).

## The lens dimension (cross-cutting coverage)

Vectors ask **one big question**; lenses ask small, repeatable checks the fleet must not be allowed to skip just because a child got assigned a different angle. A lens has an owner (≥1 pass exercises it), a checklist, a route, and an optional deterministic accelerator. The code-hygiene family — the stage-3 gap from our phase-2 lens comparison — is defined in [hygiene-lens.md](hygiene-lens.md).

Every run manifest renders a **lens matrix** — a closed table of lens × owning passes:

```text
LENS TABLE (run <head OID>)
lens    | owner(s)              | mechanical | trail
type    | deterministic preflight | yes       | lens
dead    | preflight + v3        | yes       | lens
read    | v2 split + v3 split   | no        | lens
name    | v3 split              | no        | lens (NOT-A-HIT when clear)
yagni   | yagni pass (when active) | no    | lens
quality | v3 split              | no        | lens
```

Rules:

1. **Per-lens coverage is a preflight assertion.** If any **active** lens has no owner, the run does not start — coverage is proven per lens, not per vector. Lenses owned by a skipped optional pass are **inactive** (matrix shows `off`) and need no owner.
2. **A lens outcome is `checked-and-clear` + a trail.** A lens not checked is a frame error, never "nothing found".
3. **Hygiene hits route to the lens trail**, never the bug/debt table (see hygiene-lens.md). Lens hits are never external: they stay in the notebook (see evidence-format.md, External routing).
4. **The family is extensible.** Adding a lens is an auditable manifest change, not silent scope drift.
5. **`quality` is advisory** (quality-lens.md): LOW default, MED only when the
   quality problem's own scale is material, never HIGH, rated independently of
   product criticality — suggestion-only on the lens trail.

## Optional pass: yagni (size / YAGNI)

Beyond the three vectors sits one **optional, vector-shaped pass**: yagni — is
the PR's physical size in lines changed justified by its contract, and what is
YAGNI? It runs only when the operator enables it (intake checkbox or on-demand
after the Vector 3 gate), post-handoff in a fresh context, on the same pinned
manifest. It owns the `yagni` lens while active (yagni-pass.md); when skipped,
that lens is inactive (`off`) and needs no owner. Hits route to the lens trail,
never the bug/debt table.

## When NOT to run the full pipeline

- Trivial/merge-bot PRs: run Vector 1 only, single pass — and never the yagni pass.
- Pre-merge iterations you already reviewed: run the closure loop, not the fleets.
- Repo unreachable or unindexed: run preflight, take the fallback (git/rg), or stop.