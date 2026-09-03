# yagni-pass.md — the optional size / YAGNI challenge

**Trigger:** operator-enabled only — at intake (KICKOFF vectors checkbox) or
on-demand after the Vector 3 gate. **Designed to run post-handoff in a fresh
context**: same run manifest, same subject tree (subject_oid), prior findings as leads.
The operator's launch prompt, verbatim:

> now let's look at the codebase from one more distinct vector after handoff to
> a new context: see if you can challenge/justify the physical size in lines
> changed of this PR or is something looking like candidates for YAGNI?

**Question:** is this PR's physical size in lines changed justified by its own
contract — and what is YAGNI?

**Fleet group:** `code-review`. **Stance:** *challenge or justify every
meaningful chunk; never redesign.*

## Grounded, not blind

The pass reads the run manifest + the contract at `contract_ref` + the full
base..subject diff, AND the V1–V3 findings pages — so it understands the
requirements and where the PR is coming from. Prior findings are **leads, not proof**: every row still needs
independent subject-tree evidence. The coordinator links duplicates at
aggregation; it never "reminds" the child to match prior verdicts.

## Split: by distinct functionality unit

Divide the PR into **discrete systems / functionality units**, using the same
partition the earlier vectors already established (contract surfaces / sealed
concepts — see intake-and-scope.md §0.3). One child per unit, parallel, each
with the unit's file list + focused diff + contract slice + prior findings as
leads. Never a line-count trigger, never coordinator size-judgment — the PR's
own shape defines the partition.

## Lens atom (owned here while the pass is active)

| Lens | Checklist (hit = cite file:line) | Dismiss (NOT-A-HIT) | Default severity |
|---|---|---|---|
| `yagni` | untraceable hunk — added lines with no contract-claim/locked-decision trace (`git diff --stat base..subject` is the mechanical start, always available, never installs); per-unit weight disproportionate to contract weight; speculative generality (abstraction with one concrete consumer, built for a hypothetical future); dead-on-arrival path (handles a scenario the PR's own contract excludes); over-built surface vs the PR's own contract | generated/vendored/lockfile/test-fixture bulk; a hunk traceable to a backed claim; contracted/required scope; pure-unused surface → `dead` lens (link, don't duplicate) | LOW; MED when material + untraceable |

`yagni` is an active lens only while this pass runs; a skipped pass deactivates
it (the lens matrix shows `off`, exempt from the coverage assertion). Size
weight is an **assessment dimension** of `yagni`, not its own lens.

## Child return format

```text
SIZE: JUSTIFIED — <unit → claim trace summary, file:line per chunk>
   | CHALLENGED — <untraceable chunks, file:line>
Y[<id>] file:line — what — which contract claim it does NOT serve — why speculative
   — severity (LOW/MED) — origin: PR-introduced | pre-existing (base: <base>:<path>:<line>)
NOT-YAGNI: <surface checked and defended by a locked decision>
NONE: <unit> — no candidates
```

Evidence at the subject tree (subject_oid); origin by base-diff like every vector.

## Severity + routing

LOW/MED only — never HIGH (current harm → Vector 2; future-change cost →
Vector 3; this pass only questions existence). Suggestion-only: rows are
**non-blocking**, route to the **lens trail** (operator-suppressible per
instance, closure-classifiable) — never the bug/debt table.

## Aggregation

Verdict per unit → trail rows; CHALLENGED chunks remain lens-trail rows, never comments (draft_comment policy unchanged). Dedupe vs the V1 claim matrix
(link, don't re-adjudicate), vs V3 (boundary: V3 asks what the *next* change
pays; this pass asks whether a paying change will ever come and whether the
contract promises it), and vs `dead` trail rows (pure-unused links there).
