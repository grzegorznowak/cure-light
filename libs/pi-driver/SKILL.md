---
name: cure-light-pi-driver
description: Binds the cure-light PR review pipeline to the pi session notebook, handoff, and model-groups plugin. Use after fetching the cure-light kernel when this runtime provides the pi notebook; runs the quick requirements check, compiles the run plan into the notebook, and seals it via handoff for the kickoff context. Requires pi with notebook_index/notebook_read/notebook_write/handoff/spawn; optional model-groups plugin for fleet groups.
---

# cure-light pi driver

The pi binding for the cure-light pipeline. It answers two questions the kernel deliberately leaves to the runtime:

1. **Can this runtime run the fleet at all?** (requirements check)
2. **Where does the review state live between phases and across handoff?** (notebook plan contract)

## When to read

After fetching the kernel (BOOTSTRAP step 9–11), read this skill and its two references. They define how to verify the runtime and how to compile the run plan into the notebook.

## Boot sequence (pi)

1. Run the **quick requirements check** — `references/requirements-check.md`.
2. Ask the intake fields once (owner/repo, pr, vectors, draft_comment, pauses, checkout_policy) — from the kernel's initialization contract.
3. **Compile the run frame** to the notebook per `references/notebook-plan-contract.md`: `pipeline-frame-<owner>-<pr>` (frozen options + head/base OID) + `pr-<n>-review` (findings skeleton).
4. **Seal then handoff** when `handoff` is available: write the compiled frame + the kickoff instruction so the next context resumes from the sealed compile without re-reading the kernel. Only call `handoff` if this runtime actually provides it.
5. If no `handoff`: continue in-session (the notebook pages still carry the state).

## Runtime assumptions (verify, don't assume)

- The **model-groups plugin** may or may not be present. Fleet groups (`flash`, `code-review`, …) exist only when it is. Check `pi.tools`/group list once; if absent, fall back to inherit-parent spawning (child inherits the parent model) or the `planner`/`coder` groups, and state the fallback in the frame.
- The **chunkhound** tools may or may not be indexed. Research tools are optional: git + bash + the repo itself are the always-available evidence base. Never block on an unindexed corpus — fallback to `git diff`/`rg`.
- **notebook** is the shared memory, not a database: no CAS, no audit — the plan contract is about page naming and ownership, not durability guarantees.

## Durability note (mirrors PhormOS)

The notebook advertises replay convenience, not a durability claim. The run frame and findings survive turns/compaction/handoff in the same pi installation; a fresh machine with no notebook history starts a new run (the manifest's head/base OID in the frame is the continuity anchor, not the notebook).