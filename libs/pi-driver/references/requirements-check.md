# requirements-check.md — preflight, ground truth not optimism

Run BEFORE the fleet spends anything. Each line is a hard gate with a fallback or a stop.

## Hard requirements

| # | Check | Command(s) | Fail → |
|---|---|---|---|
| 1 | gh authenticated, repo scope | `gh auth status` | STOP (review needs review-comment drafting) |
| 2 | target repo reachable | `gh repo view <owner>/<repo>` | STOP |
| 3 | PR exists, OPEN; base OID + remote head OID captured (informational) | `gh pr view <pr> --json headRefOid,baseRefOid,state,title` | STOP or ask |
| 4 | subject tree pullable: repo reachable for clone/worktree, OR (pi-chhound) `/ch-status` responds | `git -C <dir> rev-parse` ; `gh repo view` ; `/ch-status` | fallback: plain-worktree path; clone if missing; no tree at all → STOP |
| 5 | (chhound rail, when plugin present) sandbox created + bridge connected at Phase 0; prefixed tool responds | `/ch-mcp … --prefix chh_pr<n>` ; `chh_pr<n>_daemon_status` | reconnect once; else record fallback (git/rg), never stop |
| 6 | notebook writable (pi) | `notebook_index` returns pages | fallback: session-scratch dir; note durability loss |
| 7 | fleet groups present (pi + model-groups) | inspect group list (flash/code-review/…) | fallback: inherit-parent spawn, note in frame |
| 8 | git diff base..subject works on the pulled tree | `git diff <base>..<subject> --stat` | use `gh pr diff` instead |
| 9 | (chhound rail) index health | `chh_pr<n>_daemon_status` | use bash/rg/grep; never block |

## Fallback policy

- Research tools missing → git diff, `rg`, `grep`, direct `read`. Evidence quality stays the same; cost rises a little.
- Fleet groups missing → single-agent review with inherit-parent spawning; the pipeline still runs, each "child" is a serialized pass. Note the downgrade in the frame.
- Notebook missing → scratch dir with the same page layout; findings survive until context compaction (warning given).

## Stop conditions

- gh auth or repo unreachable → stop; the review has no output channel and no evidence base.
- No subject tree and clone/pull fails → stop.
- (chhound rail) plugin present but sandbox/connect/index broken → recorded fallback (plain worktree + git/rg), never a stop by itself.

## Output of the check

A short table: `requirement (ok | fallback) | evidence`. Written into the run frame. If anything fell back, the frame says so — the closure loop and any later context must know the evidence base was narrower.