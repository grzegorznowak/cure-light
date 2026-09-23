# yagni-pass.md — the optional over-engineering / YAGNI challenge

**Trigger:** operator-enabled only — at intake (KICKOFF vectors checkbox) or
on-demand after the Vector 3 gate. **Designed to run post-handoff in a fresh
context**: same run manifest, same subject tree (subject_oid), prior findings as leads.
The operator's launch prompt, verbatim (historical):

> now let's look at the codebase from one more distinct vector after handoff to
> a new context: see if you can challenge/justify the physical size in lines
> changed of this PR or is something looking like candidates for YAGNI?

The pass still runs optional and fresh-context as launched; its current
semantics are narrower: **over-engineering of the claimed delivery**. Size
accounting is Vector 1's changed-unit accounting, and a mechanism's mere
traceability to a claim no longer justifies it.

**Question:** is the engineering used to deliver the claimed behavior justified, or over-built?

**Fleet group:** `code-review`. **Stance:** *challenge unnecessary
mechanisms; never redesign.*

## Grounded, not blind

The pass reads the run manifest + the contract at `contract_ref`, the V1–V3
findings pages and the state's **symbol map** (`symbol_sweep` — chhound-driver.md,
Symbol sweep), and it consumes the coverage ledger's **EXPLAINED range groups**
plus the claim matrix as leads — so it sees which behavior each range was
accepted to deliver and where the contract's claims sit. It never ingests the
global diff: reads are scoped to the unit at hand.

A claim GAP may coexist with explained ranges: keep the gap context, never
exclude an imperfect implementation. Prior findings are **leads, not proof**:
every row still needs independent subject-tree evidence. The coordinator links
duplicates at aggregation; it never "reminds" the child to match prior verdicts.

## Split: by distinct functionality unit

Divide the PR into **discrete systems / functionality units**, using the same
partition the earlier vectors already established (contract surfaces / sealed
concepts — see intake-and-scope.md §0.3). One child per unit, parallel, each
with the unit's file list + focused diff + contract slice + its EXPLAINED range
groups + prior findings as leads. Never a line-count trigger, never coordinator
size-judgment — the PR's own shape defines the partition.

## Lens atom (owned here while the pass is active)

| Lens | Checklist (hit = cite file:line) | Dismiss (NOT-A-HIT) | Default severity |
|---|---|---|---|
| `yagni` | unnecessary mechanism serving a claimed behavior: speculative generality (abstraction with one concrete consumer and no present justification); config for one fixed value; dead-on-arrival scenario the PR's own contract excludes; needless layers/options/extension surface; implementation weight disproportionate to the claimed behavior. One consumer or config value is *evidence to investigate*, not automatic guilt | a concrete present requirement / locked constraint justifies the mechanism; the simpler-looking substitute loses required behavior; genuine generation bulk | LOW; MED when material and no present justification exists |

An `EXPLAINED` unit is **not dismissed** as NOT-A-HIT: "the feature was
required" does not mean every abstraction it shipped was. Accounting for units
with no claim link belongs to Vector 1; this pass asks only whether what a
claim *did* deliver is over-built.

`yagni` is an active lens only while this pass runs; a skipped pass deactivates
it (the lens matrix shows `off`, exempt from the coverage assertion).

## Child return format

```text
ENGINEERING: JUSTIFIED — <unit → served claim, file:line per mechanism, why required>
   | CHALLENGED — <unit → unnecessary mechanism, file:line>
Y[<id>] file:line — served claim: <claim_id / locked decision> — unnecessary mechanism:
   <what> — present justification missing: <why the requirement does not need it>
   — severity (LOW/MED) — origin: PR-introduced | pre-existing (base: <base>:<path>:<line>)
NOT-YAGNI: <surface checked and defended by a locked decision>
NONE: <unit> — no candidates
```

Evidence at the subject tree (subject_oid); origin by base-diff like every vector.

## Severity + routing

LOW/MED only — never HIGH (current harm → Vector 2; future-change cost →
Vector 3; this pass only questions existence). Suggestion-only: rows are
**non-blocking**, route to the **lens trail** (operator-suppressible per
instance, closure-classifiable) — never the bug/debt table. Pure unused
surface → `dead` lens (link, don't duplicate). `EXCLUDED` accounting is not
quality clearance; an explicit operator extension may ask about unclaimed units
without changing their V1 attribution.

## Aggregation

Verdict per unit → trail rows; CHALLENGED chunks remain lens-trail rows, never comments (draft_comment policy unchanged). Dedupe vs the V1 claim matrix
(link, don't re-adjudicate), vs V3 (boundary: V3 asks what the *next* change
pays; this pass asks whether a paying change will ever come and whether the
contract promises it), and vs `dead` trail rows (pure-unused links there).
