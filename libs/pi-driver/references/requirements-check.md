# requirements-check.md — preflight, ground truth not optimism

Run BEFORE the fleet spends anything. Each line is a hard gate with a fallback or a stop.

## Hard requirements

| # | Check | Command(s) | Fail → |
|---|---|---|---|
| 1 | gh authenticated, repo scope | `gh auth status` | STOP (review needs comment/issue drafting) |
| 2 | target repo reachable | `gh repo view <owner>/<repo>` | STOP |
| 3 | PR exists, OPEN, head+base OID captured | `gh pr view <pr> --json headRefOid,baseRefOid,state,title` | STOP or ask |
| 4 | local checkout present OR cloneable | `git -C <dir> rev-parse` ; else `git clone` | clone; if no network access to repo, STOP |
| 5 | checkout == PR head (or policy allows otherwise) | `git log -1` vs `headRefOid` | fetch+checkout pinned head; `require_pr_head` → refuse diverged tree |
| 6 | notebook writable (pi) | `notebook_index` returns pages | fallback: session-scratch dir; note durability loss |
| 7 | fleet groups present (pi + model-groups) | inspect group list (flash/code-review/…) | fallback: inherit-parent spawn, note in frame |
| 8 | git diff base..head works locally | `git diff <base>..<head> --stat` | use `gh pr diff` instead |
| 9 | (optional) chunkhound research/index ready | `chunkhound_daemon_status` | use bash/rg/grep; never block |

## Fallback policy

- Research tools missing → git diff, `rg`, `grep`, direct `read`. Evidence quality stays the same; cost rises a little.
- Fleet groups missing → single-agent review with inherit-parent spawning; the pipeline still runs, each "child" is a serialized pass. Note the downgrade in the frame.
- Notebook missing → scratch dir with the same page layout; findings survive until context compaction (warning given).

## Stop conditions

- gh auth or repo unreachable → stop; the review has no output channel and no evidence base.
- No checkout and clone fails → stop.
- Checkout ≠ head and `require_pr_head` → stop with the divergence shown.

## Output of the check

A short table: `requirement (ok | fallback) | evidence`. Written into the run frame. If anything fell back, the frame says so — the closure loop and any later context must know the evidence base was narrower.