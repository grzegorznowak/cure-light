# implementation-pass.md — Vector 2: does the shipped code work?

**Question:** does the implemented code work safely, hold its invariants, and fail correctly?

**Fleet group:** `code-review`. **Stance:** *find user-visible correctness / compatibility / validation / state-transition bugs; classify origin; do not propose large refactors.*

## Split

By **sealed concept / invariant** — each child owns one data flow or invariant the review already established, NOT an open-ended file sweep. Examples from a real run:

- derivation core edge cases (ordering, empty sets, casts)
- persistence atomicity / security / version boundaries
- spawn fail-early reachability + session lifecycle
- orchestration / TUI escaping, focus, state retention
- test integrity (would a regression stay green?)

The split is derived from the Vector 1 matrix — you drill into the surfaces that carry contract weight, not every line.

## Origin classification (mandatory)

Every finding gets an origin, decided by **base-diff evidence**, never vibes:

- **PR-introduced** — the code path is new to this PR (new field, new gate, new logic).
- **Pre-existing** — present at the PR base; the PR may touch the area but did not create it.

Verify by diffing the base commit (`git show <base>:<path>`) and citing where the mechanics come from. This feeds the disposition below.

## Child return format

```text
[F<id>] file:line — what — concrete failure mode (exploit or user-visible) — severity (HIGH/MED/LOW)
origin: PR-introduced | pre-existing (base evidence: <base:<path>:<line>)
```

- Label `NOT-A-BUG` when a suspected bug is checked and dismissed (cheap, honest).

## Hygiene lenses owned here

Vector 2 owns the **`read` lens** (readability / statement density) — see [hygiene-lens.md](hygiene-lens.md). Concretely:

- Each split names the `read` checks it exercised and marks `NOT-A-HIT` when clear — a lens not named is a frame error, never silence.
- A one-line expression packing several side effects, or a branch whose intent is not spottable in a glance = a `read` lens hit (LOW, lens trail). Naming/shape-lies belong to the `name` lens (owned by Vector 3), not `read`.
- Dense-but-repo-idiomatic code is a `NOT-A-HIT`, not a hit — the repo's own style is the baseline, never an invented one.

**Style rule reconciled**: hygiene findings are *detected* by Vector 2 splits but do not enter the bug table — they route to the lens trail with LOW default severity and are operator-suppressible per instance. What the old rule forbade is *unrouted style noise in bug findings*; it never forbade systematic detection.

## Aggregation + disposition

The coordinator segments findings into:

1. **In-scope / pre-existing** → route per evidence-format.md (External routing): rows for the single review comment's Findings or "Potential follow-up issues" sections.
2. **Deferred** → recorded on the decisions page with rationale; never presented as fixed.

Hygiene lens hits (from the section above) are aggregated **separately** into the lens trail of the findings page — not merged into the bug table — and each stays operator-gated.

Also produce the **pre-existing vs PR-introduced summary** — the operator needs to see directly which debt the PR itself owes and which it merely inherits.

## Failure to avoid

- **Re-verifying Vector 1.** Vector 2 assumes conformance status is known; it hunts bugs, not contract gaps.
- **Missing the origin.** A pre-existing issue mislabeled as PR-introduced floods the review comment; a PR-introduced one mislabeled as pre-existing lets the PR merge with a regression.
- **Asserting bugs without reproduction path.** HIGH findings need the concrete failure sequence.
