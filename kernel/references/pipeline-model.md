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
Intake → Phase 0 → Vector 1 → Vector 2 → Vector 3 → Output → Closure loop (on new head)
```

- Vector 2 runs only when Vector 1 has a clean/accepted disposition (or the operator explicitly allows skipping).
- Vector 3 runs only when the implementation evidence is stable.
- The operator gates between phases. No autonomous new-commit loops.

## Cross-cutting rules

1. **One pinned subject.** All vectors analyze the same head OID (see intake-and-scope.md).
2. **Origin classification is mandatory** (pre-existing vs PR-introduced), decided by base-diff.
3. **Two-axis severity**: impact (HIGH/MED/LOW) × disposition (fix-in-PR / pre-existing-debt / deferred-decision).
4. **Notebook is the shared memory.** The coordinator writes run frame + findings pages; children return compact evidence records, they do not compete for writes.
5. **Inconclusive = not pass.** Child timeout/truncation means the finding is unverified, not accepted.
6. **Fleets are budgeted.** Per-phase child counts, timeouts, output caps, and a cheap re-review path (delta-only) are mandatory.
7. **Review is diagnostic.** cure-light proposes; the operator gates every external artifact (gh comment, gh issue).

## When NOT to run the full pipeline

- Trivial/merge-bot PRs: run Vector 1 only, single pass.
- Pre-merge iterations you already reviewed: run the closure loop, not the fleets.
- Repo unreachable or unindexed: run preflight, take the fallback (git/rg), or stop.