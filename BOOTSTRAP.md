# cure-light — Remote Boot

Boot a **cure-light PR review episode** without cloning or installing anything locally. Everything resolves against `main`.

## Raw base

```text
RAW_BASE = https://raw.githubusercontent.com/grzegorznowak/cure-light/main
```

## Files to fetch

These seed the session so it can compile the review process. Fetch them in order as **raw** markdown — preserve every byte, never use a summarizer or paraphrase.

### Kernel (the review method)

1. `$RAW_BASE/kernel/SKILL.md`
2. `$RAW_BASE/kernel/references/pipeline-model.md`
3. `$RAW_BASE/kernel/references/intake-and-scope.md`
4. `$RAW_BASE/kernel/references/conformance-pass.md`
5. `$RAW_BASE/kernel/references/implementation-pass.md`
6. `$RAW_BASE/kernel/references/debt-pass.md`
7. `$RAW_BASE/kernel/references/closure-verification.md`
8. `$RAW_BASE/kernel/references/hygiene-lens.md` — the lens dimension (code-hygiene family, deterministic preflight, lens trail)
9. `$RAW_BASE/kernel/references/yagni-pass.md` — the optional size/YAGNI pass (fresh-context, post-handoff)
10. `$RAW_BASE/kernel/references/quality-lens.md` — the `quality` lens (V3-owned: maintainable shape, suite strength, consistency)
11. `$RAW_BASE/kernel/references/chhound-driver.md` — the chunkhound research rail (pi-chhound plugin): sandbox pull, MCP connect, tool names, discovery-only rule
12. `$RAW_BASE/kernel/references/evidence-format.md`

### Pi driver (notebook + handoff + model-groups binding — only if this runtime provides the pi notebook)

13. `$RAW_BASE/libs/pi-driver/SKILL.md`
14. `$RAW_BASE/libs/pi-driver/references/requirements-check.md`
15. `$RAW_BASE/libs/pi-driver/references/notebook-plan-contract.md`

### Templates / assets (keep for reference during the episode)

16. `$RAW_BASE/templates/KICKOFF.md`
17. `$RAW_BASE/assets/finding-schema.json`
18. `$RAW_BASE/assets/child-pass-prompt-template.md`

### Worked example (optional, read after compiling the process)

19. `$RAW_BASE/docs/example-review.md`

## Fetching rules

- Use `curl -sL <url>` or an equivalent raw-download tool.
- Do **not** summarize, paraphrase, or truncate. The kernel text is normative.
- Hold the fetched text in a scratch location you can re-read during the session.
- Report `file: <line-count>` for every file before proceeding.

## After fetching

1. Run the **quick requirements check** (pi-driver `requirements-check.md`).
2. Ask the **intake fields once** (from `KICKOFF.md` — see below for the field list).
3. Compile the run frame and save it to the notebook per `notebook-plan-contract.md`.
4. If `handoff` is available in this runtime, seal the compiled frame and hand off so the next context starts from the sealed compile and runs **Phase 0 → Vector 1**. Else continue in-session.
5. Report the requirements-check result and the compiled plan before proceeding.

## Bootstrap prompt (paste into a fresh session)

> Boot a cure-light PR review episode from the remote manifest at
> `https://raw.githubusercontent.com/grzegorznowak/cure-light/main/BOOTSTRAP.md`
> Fetch the manifest, then follow its instructions exactly: fetch the listed
> files as raw markdown (no summarization, preserve bytes), report each file's
> line count, run the quick requirements check, ask the intake fields once
> (owner/repo, PR number, vectors, auto-draft policy — from KICKOFF.md), compile
> the run plan into the notebook, and — because this runtime provides the pi
> notebook + handoff — seal the compiled frame and hand off so the next context
> kicks off Phase 0 (pull subject + contract) then Vector 1. Report the requirements
> result and the compiled plan back before proceeding. No clone or install.