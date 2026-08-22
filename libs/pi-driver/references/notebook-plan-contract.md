# notebook-plan-contract.md — where review state lives

The notebook is the shared memory between phases, children, and handoff contexts. The coordinator owns writes; children return compact records and never race pages.

## Page layout

| Page | Owner | Contents | Lifetime |
|---|---|---|---|
| `pipeline-frame-<owner>-<pr>` | coordinator (intake) | frozen run options, head/base OID, changed-file list, contract path, fallback notes | one run; a head move starts a NEW frame (linked by diff), never overwritten in place |
| `pr-<n>-review` | coordinator (append per vector) | findings table (schema rows) + closure table | one PR, all runs |
| `dis-<n>-review` (or the durable `decisions` page when follow-ups survive) | coordinator | deferred-decision + closed-by-operator records: author/time/rationale/scope | durable |

Reference pages by name. Children `notebook_read` on demand; they do not preload bodies. The coordinator serializes writes with a process-local ordering so same-name writes don't race.

## Content rules

- **Findings are recoverable facts** — keep the evidence-format rows; discard tender re-derivable code trivia freely at handoff.
- **Decisions are non-recoverable** — always persist: operator deferrals, closed-by-operator records, locked decisions from the issue. Never let them go stale or vanish on compaction.
- **No raw transcripts/logs.** A vector's dead ends and working notes do not belong in the notebook; the closure table's `re-opened` row records the reason concisely.

## The seal-then-handoff step

When `handoff` is available and the operator confirms the frame:

1. Write `pipeline-frame-<owner>-<pr>` (compiled options + manifest) and `pr-<n>-review` (findings skeleton).
2. Discard recoverable code-trivia pages; refresh the durable decision page.
3. Draft the handoff prompt that carries ONLY: the frame's location, the current state (intake complete, requirements pass/fallback), the immediate next step (Phase 0 pin + contract → Vector 1), and any blocker or failed path worth avoiding.
4. Call `handoff` with `discardPages` for code-trivia pages and the task prompt pointing at the frame page by name.

The next context reads the frame page, loads kernel references on demand, and kicks off Phase 0 → Vector 1 — it does not re-fetch the kernel.

## If no handoff

Continue in-session; the frame and findings pages still carry the state. The operator sees the compiled plan inline instead of via a fresh context.