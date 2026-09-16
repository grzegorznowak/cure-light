# blast-lens.md — the `blast` lens: data × call-site blast radius

A diff and a legacy row each look harmless alone; only their interaction is the
incident. Vector 2 owns one always-active advisory lens, **`blast`**, that forces
the question the diff alone cannot answer:

> **What existing data and call sites will meet this change — and is the
> hazard's instance proven?**

The lens is **not hygiene** — nothing in it is style or unused surface. It is
the data-facing half of "does the shipped code actually work safely?", and it
routes differently from the rest of the family: its **rows are advisory, its
instance is a finding** (see Routing).

## Owner and activation

- **Owner:** the **deterministic preflight** runs the mechanical `sweep` once
  per review state — its table is the manifest's `symbol_sweep` artifact
  (recipe: chhound-driver.md, Symbol sweep) — and each Vector 2 split owns the
  four judgment rows (`data` / `semantics` / `fixture` / `gates`) and consumes
  that table. A lens without an owner is a frame error (hygiene-lens.md).
- **Activation:** always active whenever Vector 2 runs. A data-free diff records
  one whole-lens `n/a` **citing the absence** of any runtime data path, shared
  value, or gate claim across the whole diff; a per-split `n/a` always carries a
  reason. A Vector-1-only run leaves the lens inactive (`off` in the matrix) —
  the coverage assertion binds active lenses only (pipeline-model.md).
- **Trail discipline:** unless the cited run-level whole-lens `n/a` applies, each
  split records every **owned** row as `hit` / `NOT-A-HIT` / `n/a-with-reason`;
  the preflight records `sweep`. A required outcome not recorded is a frame error
  (`inconclusive`), exactly like an unnamed lens (implementation-pass.md).

## The five rows

| Row | Checklist (hit = cite file:line) | Dismiss (NOT-A-HIT) | Determinism |
|---|---|---|---|
| `data` | the changed behavior depends on state the PR does not create — legacy / orphan rows, dangling refs, NULL / empty / anonymous state, zero-value sentinel rows; name the concrete data state that reaches it | the surface is new or self-contained: no pre-existing rows or consumers can reach it | low — entry points are findable; the reachability call is judgment |
| `sweep` | a changed shared sentinel / constant / default: every consumer must be enumerated **in this PR**; a call site named as deferred ("follow-up ticket") or simply uninspected = hit | the sweep table exists with no uninspected remainder and every `outside` hit is accounted for — a verified consumer, or routed as a finding (cite the table) | **high** — the preflight symbol-sweep recipe (chhound-driver.md, Symbol sweep: `rg` census + rail `search` triage); always available, never installs |
| `semantics` | a comparison where the language's value model differs from the storage engine's (e.g. empty string vs a numeric column): the column type and the engine's own meaning are checked at the site | the comparison is proven type- and engine-consistent (cite the column / schema definition) | medium — schema definitions are findable; the meaning call is judgment |
| `fixture` | a hazard whose trigger is a **single artificial row/state** is being adjudicated on inspection alone → the requirement is on the **PR** to ship the fixture test that reproduces it on the repo's own scratch database; the review flags the absence, never runs it | no artificial-state trigger exists, or the PR already ships the reproducing fixture | low (judgment) — the repo's own harness runs the test; the fleet never installs or executes a database |
| `gates` | a "this class is statically detectable" claim where the analyzer / lint gate is **not enabled** in the repo's own config or CI — a dormant analyzer is not a net | no static-detectability claim is made, or the gate is enabled and cited | medium — read the repo's CI + analyzer config; no installs |

Reading finds the hazard **class**; only a fixture proves the **instance**.

## Routing: advisory rows, blocking findings

- **Rows → lens trail.** LOW by default, MED when the problem's own scale is
  material, **never HIGH**; suggestion-only, operator-suppressible per instance,
  notebook-only. They never enter the bug/debt table and never the comment
  (evidence-format.md, External routing) — the one mechanical exception is the
  preflight table surfaced as the comment's `Symbol impact` section.
- **The concrete instance → the bug table.** A **concrete instance** is a named
  file:line mechanism + a named trigger (data / input / config) + a concrete
  failure mode; anything less stays a row hit. An instance is a **Vector 2
  finding** at its own severity (HIGH possible). That finding is what blocks;
  the lens only finds the class. Cross-cutting rule 1 holds unchanged: **a lens
  never blocks vector gating by itself** (hygiene-lens.md).
- **A deferred / uninspected consumer is in scope.** The PR introduced or
  enforced that path, so it routes as a visible **Vector 2 finding in the bug
  table**, to be addressed — never auto-downstreamed (evidence-format.md, Scope
  routes the comment). The `sweep` coverage row itself stays trail-only.

## Determinism

The `sweep` row is mechanical: the preflight recipe produces the once-per-state
table (chhound-driver.md, Symbol sweep — `rg` census, rail `search` triage), which
the matrix renders `yes (sweep)`. `semantics` / `gates` read subject-tree files
(schema/migration definitions, CI and analyzer config); `data` / `fixture` are
fleet judgment. A sweep that cannot run is `inconclusive-mechanical` in the
trail (evidence-format.md) — never a silent skip.

## Boundaries (dedupe map)

- **`dead` lens** — unused surface that never runs; `blast.data` is *existing
  data* reaching code that does run.
- **`type` / `dead` preflight** — the compiler/lint net; the `sweep` row is a
  different mechanical net (a changed literal's consumers, not unused symbols).
- **Test surfaces** — `quality.test` is residual suite strength, the V1 Tests
  surface is contract-claim existence, V2 test integrity is a demonstrated
  regression that stays green; `blast.fixture` is triggered differently — a
  hazard the review discovered whose only evidence is inspection.
- **V3 debt** — repo-wide consistency and future-change cost; a repo-wide sweep
  completeness claim is V3's search-extensive territory (debt-pass.md) when the
  operator wants the extra coverage — the default owner stays V2 + preflight.
- **`quality` / `yagni`** — shape and existence of what should exist; the `blast`
  lens asks whether what exists is safe against the data already in the
  database.
