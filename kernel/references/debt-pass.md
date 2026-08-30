# debt-pass.md — Vector 3: is the way it's built sustainable?

**Question:** what costs will the *next* change to this subsystem pay, because of how this PR delivered its feature?

**Fleet group:** `code-review`. **Stance:** *identify future-change cost or divergent ownership; distinguish design debt from bug; never line-by-line.*

## Split

By **bigger concepts**, drilled down from what Vectors 1–2 already established. Standard axes (pick the ones that apply):

1. **Pluggability / extensibility claim** — is an advertised "pluggable" surface real, or a hard-coded vertical slice? (The classic: a spec says "extensible to X constraints"; code ships one hard-coded constraint type. Count the touch points a 2nd type needs.)
2. **Boundary ownership** — which module owns what; does a persistence module now depend on host model resolution; are cap-invariants enforced at the right layer?
3. **Versioning / migrations** — is the version logic centralized or scattered with literal numbers; is refusal-to-downgrade a dead-end; any migration dispatcher?
4. **Projection / state representation** — derived vs persisted shapes; do transient fields leak into durable config; is there a projection boundary?
5. **Performance / operability** — unbounded re-derivation, missing caches/invalidation, unbounded fleet cost.
6. **Vocabulary / source-of-truth** — is there one enum/const, or re-declared prose/schemas that drift?

## Hygiene lenses owned here

Vector 3 co-owns the **`dead`**, **`read`** and **`name`** lenses (see
[hygiene-lens.md](hygiene-lens.md)) — a dead feature or unused surface is
*future-change cost*, which is exactly this vector's question:

- `dead` — exported/surfaces the PR leaves un-consumed, dead config/keys, commented-out feature blocks; hit = LOW, but **MED** when removing the symbol would change behavior (a live surface that just looks dead).
- `read` — statement density at the *concept* level: one axis doing several jobs, a shape that can't be parsed in one glance.
- `name` — vocabulary drift vs the repo's own source-of-truth term; a name that lies about its shape.
- `quality` — Vector 3 owns the **`quality`** lens outright (see
  [quality-lens.md](quality-lens.md)): big decision trees that outgrew their
  shape, coverage-without-assurance, error-handling drift, duplication — all
  four sub-checks are future-change cost, this vector's question. Every debt
  split records `tree` / `test` / `error` / `dupe` as hit / NOT-A-HIT /
  n/a-with-reason.

Routing priority for `quality` candidates: a *correctness / observability*
failure belongs to Vector 2; a *concrete future-change cost* is a debt finding;
only residual advisory shape / idiom / suite-strength concerns become
`quality` rows (link, don't duplicate).

All hygiene hits route to the lens trail (LOW default, operator-suppressible), not the debt table.

Each child receives: contract context, the relevant architecture files + diff, and this stance. Reading is concept-directed, not exhaustive.

## Child return format

```text
[D<id>] concept — why fragile/short-lived — concrete future failure when <2nd constraint | next version | new host> arrives — severity (HIGH blocks future feature work / MED / LOW)
```

- Verify with file:line where the shape is hard-coded.
- A debt must be *worth tracking*: if no future change pays it, it's noise.

## Aggregation + disposition

The coordinator groups findings:

1. **Concept-level finding + concrete future failure.**
2. **PR-specific vs pre-existing** segmentation (debt can live on pre-existing flows the PR compounds).
3. **Disposition**: `fix-in-PR` / `deferred-decision` (recorded, with rationale) / `tracked-separately` (own ticket).

## Failure to avoid

- **Presenting debt as bug.** Debt lacks a current failure; if there is a live failure path, it belongs in Vector 2.
- **Unchecked "extensible" claims.** An aspiration in the spec is a debt when the code doesn't back it — verify, don't take the claim's word.
- **Hiding defers.** Acknowledged-but-unfixed debt must be recorded, not silently dropped.