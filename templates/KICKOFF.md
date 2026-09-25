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

- [x] Conformance (are the PR's claims delivered and every changed unit accounted for?)
- [x] Implementation bugs (does the shipped code work?)
- [x] Code debt (is the way it's built sustainable?)
- [ ] Yagni — optional pass (is the engineering used to deliver the claimed behavior over-built? any YAGNI?)
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
> `before_post` is **enforced** — not optional — whenever `draft_comment` is enabled.

```
- [ ] after intake (frame confirmation)
- [x] after each vector
- [ ] after closure re-review
```

Automatic (not a checkbox): a material unresolved contradiction between captured sources — or any other `repair_required` defect such as missing designation/orientation — pauses the run **before Vector 1**; continuing anyway takes your explicit recorded authorization (an evidence-only V1 run for a contradiction, or an explicitly limited V1-only review), and neither clears the defect.

## 7. Chhound rail (only when the pi-chhound plugin is present)

```
- [x] chunkhound PR sandbox as the review subject (recommended; plain worktree otherwise)
```

If checked and the rail is detected as installed, expect the coordinator to probe and
drive it itself (`ch-chhound`; consent prompts on the sandbox create/connect). Where model
tools are unavailable, expect one fallback request: run `/ch-status` at the frame gate and
report the output.

---

## 8. Pinned toolchain (Phase-0 prerequisites and expectations)

- **Environment**: python ≥3.11 with `uv` (or equivalent venv) available; producer deps
  pre-installed exactly (`tree-sitter==0.26.0`, `tree-sitter-markdown==0.5.1`). Missing
  deps fail loud (exit 2) — never an ad-hoc registry.
- **Engine-owned copies (D4)**: the run fetches and sha256-verifies its own pinned tool
  copies at Phase 0 — `claim-registry` 0.3.0, `gate-check` 0.2.0, `census` 0.1.0 — and
  never executes the subject tree's `tools/` (reviewed content only).
- **Producer/labeling time**: whole-source labeling costs one child call per designated
  source that fits the caps (≤16 KiB raw / ≤80 units / ≤64 KiB complete worker input);
  larger sources use bounded slices — one child call per ≤16 KiB / ≤80-unit slice
  (≤32 slices default, ≤4 concurrent, plus corrected/boundary calls). Tool compute is
  seconds; labeling is the dominant fleet cost.
- **Fail-closed**: any pin mismatch, missing dependency (exit 2), failed
  reconcile/assemble/validate/manifest, `gate-check` ≠ exit 0 with both permissions, or
  claims-page projection mismatch **stops Phase 0** — no hand-built registry, no relaxed
  gate, no auto-continue.

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
> (pull subject + contract) then Vector 1. Report the requirements result and compiled plan back before
> proceeding. No clone or install.

## What happens next (expectation set)

1. The agent fetches + reads the kernel and driver, reports line counts.
2. It runs the quick requirements check (gh auth, repo, PR OID, planned subject mechanism, pinned toolchain + producer deps, notebook, groups — the subject-tree rows defer to Phase 0).
3. It asks the intake fields **once** — usually nothing is missing if KICKOFF is filled.
4. It compiles the run frame and shows it for confirmation.
5. It saves the frame + findings pages, and (if the runtime provides handoff) seals and hands off.
6. Phase 0 runs in the new context: pull the subject (the first tree read — no orientation in local target checkouts before it), compile the contract and run the pinned producer (batch capture → frame/frame-slices → labeling children → proposal-reconcile → assemble → validate → manifest → `gate-check`; the claims page is a projection of the canonical registry on pi runs, CONTRACT.md otherwise — a notebook-less fallback cannot assert complete coverage), record subject path/OID + changed files + toolchain pins into the frame, complete the deferred requirements rows, run the bounded source-consistency pass (a material unresolved contradiction between captured sources — or any other `repair_required` defect → provisional repair + default pause before V1; a named evidence-only V1 run only if you authorize it), run the census (`census run` + `check`, 0.3a), compile the capacity-bounded splits (0.3b), and show the actual counts, the exclusion policy, coverage-page location, budgets, producer gate report/permissions and consistency outcome at the Phase-0 gate.
7. Vector 1 (conformance — claim adjudication + changed-unit accounting) fleets out; report; gate — the coordinator records the review basis (`ready` / `limited-only` / `blocked` / `unknown`) and any outstanding repair requirement before Vector 2 may be planned. Then the deterministic preflight (symbol map), Vector 2, Vector 3, then output.
8. On "the implementer worked on the review", the closure loop re-validates per finding and publishes the table.