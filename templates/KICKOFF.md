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

- Phase-0 claims and join: `fast` only (pause if unavailable; no substitution)
- Conformance: `flash` only (pause if unavailable; no substitution)
- Implementation: `code-review`
- Debt: `code-review`
- Yagni (if enabled): `code-review`

Required groups are binding: a group that is absent or degenerate (present but cannot resolve to a usable model/group) pauses the affected stage — no substitution (no inherited parent, `planner`/`coder`, or other group).

## 5. Draft policy (never auto-post otherwise)

> Finalization = one aggregated review comment per run (summary, findings,
> suggested follow-up issues, footer). Potential issues are suggested inside it
> — the developer opens them; gh issue bodies are never drafted.

```
draft_comment: [false]   # review-only; draft the single review comment on explicit request
```

## 6. Pauses / operator gates

> Default: pause after each vector (`per_vector`). Tick any extra checkpoints you want.

**Mandatory gates (not checkboxes):**

- **Frame confirmation** — the frame is compiled unsealed, shown, and **waits for your explicit confirmation** before it is written, read back, and sealed/handed off (notebook-plan-contract.md).
- **Before post** — **enforced** whenever `draft_comment` is enabled.
- **Repair pause** — a material unresolved contradiction between captured sources, or any other `repair_required` defect (missing designation/orientation included), pauses the run **before Vector 1**; continuing takes your explicit recorded `repair_required.continuation` mode (an evidence-only V1 run or an explicitly limited V1-only review), and neither clears the defect nor authorizes ordinary downstream work.

Optional pauses:

```
- [x] after each vector
- [ ] after closure re-review
```

## 7. Chhound rail (only when the pi-chhound plugin is present)

```
- [x] chunkhound PR sandbox as the review subject (recommended; plain worktree otherwise)
```

If checked and the rail is detected as installed, expect the coordinator to probe and
drive it itself (`ch-chhound`; consent prompts on the sandbox create/connect). Where model
tools are unavailable, expect one fallback request: run `/ch-status` at the frame gate and
report the output.

---

## 8. Phase-0 prerequisites and expectations

- **Engine tool**: Node + git and the zero-dependency `kernel/tools/chunker.mjs` shipped with cure-light. The frame records its path, exact-byte sha256 and recipe at `cure_light_source_head_oid`; never run a subject-tree copy. No census-plugin install or private-package credential is required.
- **Sequence**: capture source bytes → `#fast` claims (`claims-draft/3`, including source consistency) → chunker units → `#fast` witnessed join JSONL → coordinator P0.5 gate. The gate is behavior, not a second shipped tool.
- **Packing/output**: full claims + whole units, in manifest order, bounded by input length only; no unit-count cap or output reservation. JSONL on disk is mandatory, appends optional. The gate checks the exact output paths and complete unit sweep, IDs/pairs/types/witnesses and recorded budgets; truncation is retried/re-split under the approved policy, never treated as “no match”.
- **Authority**: draft links mean “look here”, never “this works”. Phase 0 emits candidate-unclaimed only; V1 validates/freezes claims against captured sources, accounts for all units and alone finalizes UNCLAIMED. Material contradictions or missing designation still default to the repair pause before V1.
- **Open pilot checkpoints**: input ceiling, retry/re-split policy, suite-level claim handling and the detailed V1 contract require an operator decision; do not infer these from a simulation's numeric budget.

---

## Bootstrap prompt (paste into the first session)

> Boot a cure-light PR review episode from the remote manifest at
> `https://raw.githubusercontent.com/grzegorznowak/cure-light/main/BOOTSTRAP.md`
> Fetch the manifest, follow its instructions exactly: fetch every listed file
> as raw markdown (no summarization, preserve bytes), report each file's line
> count, run the quick requirements check, ask the intake fields once (owner/
> repo, PR number, vectors, draft policy), compile the run plan unsealed and
> show the compiled frame (with the requirements result) for explicit
> confirmation, wait for that confirmation, then write + read back the frame and
> findings skeleton and — because this runtime provides the pi notebook +
> handoff — seal the compiled frame and hand off so the next context kicks off
> Phase 0 (pull subject + contract) then Vector 1. No clone or install.

## What happens next (expectation set)

1. The agent fetches + reads the kernel and driver, reports line counts.
2. It runs the quick requirements check (gh auth, repo, PR OID, planned subject mechanism, Node/git + shipped chunker identity, Phase-0 fast availability, notebook, groups — the subject-tree rows defer to Phase 0).
3. It asks the intake fields **once** — usually nothing is missing if KICKOFF is filled.
4. It compiles the run frame unsealed and shows it for the operator's explicit confirmation — it waits there.
5. On the operator's explicit confirmation, it writes and reads back the frame + findings pages, and (if the runtime provides handoff) seals and hands off.
6. Phase 0 runs in the new context: pull the subject first; capture the verbatim contract (`contract-<owner>-<pr>-s<n>` on pi, disk fallback otherwise) and source refs/hashes; draft claims with `#fast` including source-consistency work; run the shipped chunker; propose links with `#fast` into per-box JSONL; run coordinator P0.5 checks and compile capacity-bounded vector splits. Record subject/base OIDs, changed files, chunker identity, claims/unit/join refs/hashes, counts, hard cases, exclusions and budgets; complete deferred requirement rows and show the Phase-0 gate. `repair_required` defaults to pause before V1 unless you authorize the existing named, bounded exception. Notebook-less fallback still lacks the authoritative V1 claim/coverage/gate-disposition store and cannot assert complete coverage or readiness.
7. Vector 1 (conformance — validate/freeze claims, adjudicate claims, account for all units and finalize UNCLAIMED) fleets out; report; gate — the coordinator records the review basis (`ready` / `limited-only` / `blocked` / `unknown`) and any outstanding repair requirement before Vector 2 may be planned. Then the deterministic preflight (symbol map), Vector 2, Vector 3, then output.
8. On "the implementer worked on the review", the closure loop re-validates per finding and publishes the table.