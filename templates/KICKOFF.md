# KICKOFF — cure-light episode template

> Fill the fields below (or answer them the first time the process asks), then
> paste the bootstrap prompt into a fresh session. The kernel asks each field
> once and never infers a default for what only the operator can supply.

## 1. Target repository (`owner/repo`)

```
<owner/repo, e.g. agenticoding/pi-agenticoding>
```

## 2. Pull request number (`pr`)

```
<number, e.g. 27>
```

## 3. Vectors to run

- [x] Conformance (does code match the PR's own claims?)
- [x] Implementation bugs (does the shipped code work?)
- [x] Code debt (is the way it's built sustainable?)
- [ ] Yagni — optional pass (is the change's size justified? any YAGNI?)
- [ ] Subset only: <list which>

## 4. Fleet groups (if this runtime provides the model-groups plugin)

- Conformance: `flash` (or inherited)
- Implementation: `code-review`
- Debt: `code-review`
- Yagni (if enabled): `code-review`

## 5. Draft policy (never auto-post otherwise)

> Finalization = one aggregated review comment per run (summary, findings,
> suggested follow-up issues, footer). Potential issues are suggested inside it
> — the developer opens them; gh issue bodies are never drafted.

```
draft_comment: [false]   # prepare the single review comment for operator approval
```

## 6. Pauses / operator gates

> Default: pause after each vector (`per_vector`). Tick any extra checkpoints you want.
> The `before_post` gate is **required** whenever `draft_comment` is enabled.

```
- [ ] after intake (frame confirmation)
- [x] after each vector
- [ ] before posting any external artifact
- [ ] after closure re-review
```

## 7. Checkout policy

```
- [x] require_pr_head (review only the pinned head OID)
- [ ] allow current working tree
```

---

## Bootstrap prompt (paste into the first session)

> Boot a cure-light PR review episode from the remote manifest at
> `https://raw.githubusercontent.com/grzegorznowak/cure-light/main/BOOTSTRAP.md`
> Fetch the manifest, follow its instructions exactly: fetch every listed file
> as raw markdown (no summarization, preserve bytes), report each file's line
> count, run the quick requirements check, ask the intake fields once (owner/
> repo, PR number, vectors, draft policy), compile the run plan into the
> notebook, and — because this runtime provides the pi notebook + handoff —
> seal the compiled frame and hand off so the next context kicks off Phase 0
> then Vector 1. Report the requirements result and compiled plan back before
> proceeding. No clone or install.

## What happens next (expectation set)

1. The agent fetches + reads the kernel and driver, reports line counts.
2. It runs the quick requirements check (gh auth, repo, PR OID, checkout, notebook, groups).
3. It asks the intake fields **once** — usually nothing is missing if KICKOFF is filled.
4. It compiles the run frame and shows it for confirmation.
5. It saves the frame + findings pages, and (if the runtime provides handoff) seals and hands off.
6. Phase 0 runs in the new context: pin the head, build CONTRACT.md, split vectors. Gate.
7. Vector 1 (conformance) fleets out; report; gate. Then Vector 2, Vector 3, then output.
8. On "the implementer worked on the review", the closure loop re-validates per finding and publishes the table.