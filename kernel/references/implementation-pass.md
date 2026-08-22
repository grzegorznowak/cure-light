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
- No style nits. No refactor proposals.

## Aggregation + disposition

The coordinator segments findings into:

1. **In-scope (PR-introduced)** → candidate PR comment, operator-gated.
2. **Pre-existing** → candidate gh issue (hardening ticket), operator-gated, explicitly out-of-PR scope.
3. **Deferred** → recorded on the decisions page with rationale; never presented as fixed.

Also produce the **pre-existing vs PR-introduced summary** — the operator needs to see directly which debt the PR itself owes and which it merely inherits.

## Failure to avoid

- **Re-verifying Vector 1.** Vector 2 assumes conformance status is known; it hunts bugs, not contract gaps.
- **Missing the origin.** A pre-existing issue mislabeled as PR-introduced floods the PR comment; a PR-introduced one mislabeled as pre-existing lets the PR merge with a regression.
- **Asserting bugs without reproduction path.** HIGH findings need the concrete failure sequence.