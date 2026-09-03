# requirements-check.md — preflight, ground truth not optimism

Run BEFORE the fleet spends anything. Each line is a hard gate with a fallback or a stop.

Two groups: **pre-pull rows** run at boot and feed the frame gate (they need only gh + the runtime, never a local tree); **deferred rows** (5/8/9) need the pulled subject and run at the **Phase 0 gate** — the check is marked complete only after they have run. Nothing in the target repo is cloned, checked out, or read locally before the subject pull (subject-first, kernel/SKILL.md §2).

## Hard requirements

| # | Runs | Check | Command(s) | Fail → |
|---|---|---|---|---|
| 1 | pre-pull | gh authenticated, repo scope | `gh auth status` | STOP (review needs review-comment drafting) |
| 2 | pre-pull | target repo reachable | `gh repo view <owner>/<repo>` | STOP |
| 3 | pre-pull | PR exists, OPEN; base OID + remote head OID captured (informational) | `gh pr view <pr> --json headRefOid,baseRefOid,state,title` | STOP or ask |
| 4 | pre-pull | subject mechanism planned: (pi-chhound) `/ch-status` responds → planned subject = chunkhound PR sandbox; else plain detached worktree | `/ch-status` | record the fallback mechanism in the frame; never a stop by itself |
| 5 | Phase 0 | (chhound rail, when plugin present) sandbox created + bridge connected; prefixed tool responds | `/ch-mcp … --prefix chh_pr<n>` ; `chh_pr<n>_daemon_status` | reconnect once; else record fallback (plain worktree + git/rg), never stop |
| 6 | pre-pull | notebook writable (pi) | `notebook_index` returns pages | fallback: session-scratch dir (frame/findings) + contract on disk; note durability loss |
| 7 | pre-pull | fleet groups present (pi + model-groups) | inspect group list (flash/code-review/…) | fallback: inherit-parent spawn, note in frame |
| 8 | Phase 0 | git diff base..subject works on the **pulled** tree | `git -C <subject-path> diff <base_oid>..<subject_oid> --stat` | fetch the base ref into the tree's repo and retry; if still failing → STOP |
| 9 | Phase 0 | (chhound rail) index health | `chh_pr<n>_daemon_status` | use bash/rg/grep; never block |

Row 4 semantics: presence is a **plan**, never a sandbox guarantee — `/ch-status` responding says the plugin is there, not that the sandbox will succeed; a sandbox failure at Phase 0 falls back per chhound-driver.md (plain worktree + git/rg). Row 8 is a post-pull check on the pulled tree only: `gh pr diff` NEVER substitutes the subject diff — the remote head may differ from the pulled subject, and diffing the wrong tree would corrupt scope and origin classification.

## Fallback policy

- Research tools missing → git diff, `rg`, `grep`, direct `read`. Evidence quality stays the same; cost rises a little.
- Fleet groups missing → single-agent review with inherit-parent spawning; the pipeline still runs, each "child" is a serialized pass. Note the downgrade in the frame.
- Notebook missing → scratch dir with the same page layout; findings survive until context compaction (warning given).

## Stop conditions

- gh auth or repo unreachable → stop; the review has no output channel and no evidence base.
- (Phase 0) the subject tree cannot be pulled at all → stop; no evidence base (intake-and-scope.md §0.1). Pre-pull there is deliberately no tree — the pull is the first local touch of the target repo.
- (Phase 0, row 8) the pulled tree still cannot diff base..subject after a fetch retry → stop; origin classification needs the base diff, and `gh pr diff` never substitutes it.
- (chhound rail) plugin present but sandbox/connect/index broken → recorded fallback (plain worktree + git/rg), never a stop by itself.

## Output of the check

A short table written into the run frame: `requirement (ok | fallback | deferred-to-Phase-0) | evidence`. The frame's **planned subject mechanism** line gives the operator boot-time visibility of how the subject will be pulled — presence, not a guarantee. Rows never mix pre/post-pull results; the check is marked complete only after the deferred rows ran at the Phase 0 gate. If anything fell back, the frame says so — the closure loop and any later context must know the evidence base was narrower.
