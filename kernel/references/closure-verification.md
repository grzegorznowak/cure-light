# closure-verification.md — the re-review loop

Triggered when the operator says the implementer "worked on the review" (or any instruction implying the PR advanced). This is **delta review**, not a pipeline re-run.

## 1. Detect the new head

```text
gh pr view <pr> --json headRefOid   → compare with the run manifest's headRefOid
```
If unchanged → say so (no work has been pushed) or wait. If changed → new head = new review state, linked to the old run by `git diff old_head..new_head`. Local checkout: verify it advanced to the new OID before trusting any diff.

## 2. Map findings → touched paths

For every open finding (and every `deferred-decision` the implementer claims to have addressed), determine which files/lines the fix would touch. The finding's evidence `file:line` is the anchor.

## 3. Re-validate per finding (targeted)

- **Code touched?** Diff the finding's path. If the relevant code is byte-identical → the finding is NOT fixed regardless of what any comment says.
- **Behavior changed?** Re-read the new code at old/new lines. Run the relevant tests if they exist and are cheap (`bun test <file>` / `node --test` style — use the repo's own runner).
- **If architecture changed** (e.g. the fix refactored the module): re-run the original fleet slice rather than spot-verify, since evidence paths moved.

## 4. Classify

| Class | Meaning | Green requires |
|---|---|---|
| `verified-fixed` | code + test evidence at old/new lines | diff addresses behavior + targeted validation passes |
| `re-classified` | category/claim changed (e.g. "bug" → "documented intentional") | honest re-framing; if it changes a HIGH, flag to operator |
| `test-only` | only tests changed; behavior identical | acknowledge; behavior finding still open |
| `doc-only` | only comments/docs changed | acknowledge; behavior finding still open |
| `deferred-decision` | acknowledged but knowingly unfixed | recorded decision + rationale, NOT presented as fixed |
| `closed-by-operator` | operator suppressed it (e.g. "don't re-raise X") | never re-raised unless new evidence outside the decision's scope |
| `re-opened` | prior proof no longer holds, or regression introduced | concrete new evidence |

## 5. Publish a closure table

```text
finding | prior evidence (old file:line) | new evidence/tests (new file:line) | class | remaining decision
```

Output to the notebook findings page, not as a fresh review. This is the artifact the operator reads to decide merge.

## 6. Honesty rules

- **Unchanged code cannot be green.** A "fixed" claim with no diff = re-open.
- **Do not present decision-deferrals as fixes.** "Locked as intentional" is a decision, not a fix — record it and surface the decision author to the operator.
- **Do not resurrect closed-by-operator items** unless the operator reopens them or new evidence clearly falls outside the suppression scope.
- **Doc/test-only closures are acknowledged as such**, so the operator knows the behavior itself is untouched.