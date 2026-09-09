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
Intake → Phase 0 → Vector 1 → Vector 2 → Vector 3 → Output (single review comment) → Closure loop (after a deliberate re-pull)
```

- Vector 2 runs only when Vector 1 has a clean/accepted disposition (or the operator explicitly allows skipping).
- Vector 3 runs only when the implementation evidence is stable.
- The operator gates between phases. No autonomous new-commit loops.

## Cross-cutting rules

1. **One stable subject per review state.** All vectors in a state analyze the same pulled tree (`subject_path` / `subject_oid`, see intake-and-scope.md); a re-pull is a new state — gated by the operator, never in-place. Findings carry the subject OID their evidence was read from.
2. **Origin classification is mandatory** (pre-existing vs PR-introduced), decided by base-diff.
3. **Two-axis severity**: impact (HIGH/MED/LOW) × disposition (fix-in-PR / pre-existing-debt / deferred-decision).
4. **Notebook is the shared memory.** The coordinator writes run frame + findings pages; children return compact evidence records, they do not compete for writes.
5. **Inconclusive = no pass.** A child timeout/truncation means the finding is unverified, not accepted.
6. **Fleets are budgeted.** Per-phase child counts, timeouts, output caps, and a cheap re-review path (delta-only) are mandatory.
7. **Review is diagnostic.** cure-light proposes; the operator gates the single external review comment (see evidence-format.md, External routing).

## The research accelerator (cross-cutting; Vector 2 + Vector 3)

Cure-light treats the chhound research rail (chhound-driver.md) as an **accelerator** for understanding the subject's subsystems — never as an evidence source. The mode is compiled from the planned subject mechanism and frozen in the run manifest at the plan gate:

- `research.mode: chhound-rail` — the rail is confirmed and Phase 0 pulls the subject as a chunkhound PR sandbox whose own index is bound under the frame's prefix `chh_pr<n>`. The manifest records the prefix and the exact tool names (`{ch_prefix}_daemon_status`, `{ch_prefix}_code_research`, `{ch_prefix}_search`) and lists every other live `chh_*` prefix as excluded.
- `research.mode: direct-tree` — plain detached worktree (rail unconfirmed/broken). The run proceeds with git/rg/read; the fallback is explicit in the manifest, never silent.

Vector 2 enforces subsystem research **mandatory-if-ready and uniform across every split — including test-integrity concepts** (deeper subsystem understanding yields better insights regardless of split type): one scoped `code_research` orientation question per sealed invariant, then at least one `search` pinpoint, then tree verification. Vector 3 enforces a **search-extensive** protocol — `search` leads every concept and lens sweep (repo-wide claims need logged searches); `code_research` may orient but is never required there. The per-child prompt slots, workflows, and the mandatory RESEARCH TRACE footer are defined in [implementation-pass.md](implementation-pass.md), [debt-pass.md](debt-pass.md) and [child-pass-prompt-template.md](../../assets/child-pass-prompt-template.md).

Authority rules (bind all vectors):

1. Index output is **discovery only**: its citations are leads, not evidence — every cited line is re-read in the subject tree at `subject_oid` before it may appear in a finding (chhound-driver.md, Evidence rule).
2. Origin (PR-introduced vs pre-existing) is decided by base diff only, never from the index.
3. Vector 1 may use the tools where the coordinator judges it useful; nothing is mandatory there.
4. Shadow splits (paired direct-only control children that measure the accelerator's quality delta) are **off by default** — enabled only by explicit operator choice (`research.shadow: on`).

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
after the Vector 3 gate), post-handoff in a fresh context, on the same run manifest and subject tree. It owns the `yagni` lens while active (yagni-pass.md); when skipped,
that lens is inactive (`off`) and needs no owner. Hits route to the lens trail,
never the bug/debt table.

## When NOT to run the full pipeline

- Trivial/merge-bot PRs: run Vector 1 only, single pass — and never the yagni pass.
- Pre-merge iterations you already reviewed: run the closure loop, not the fleets.
- Repo unreachable or unindexed: run preflight, take the fallback (git/rg), or stop.