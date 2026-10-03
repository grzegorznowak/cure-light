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
9. `$RAW_BASE/kernel/references/blast-lens.md` — the `blast` lens (V2-owned: data × call-site blast radius, advisory rows vs blocking instances)
10. `$RAW_BASE/kernel/references/yagni-pass.md` — the optional over-engineering/YAGNI pass (fresh-context, post-handoff)
11. `$RAW_BASE/kernel/references/quality-lens.md` — the `quality` lens (V3-owned: maintainable shape, suite strength, consistency)
12. `$RAW_BASE/kernel/references/chhound-driver.md` — the chunkhound research rail (pi-chhound plugin): model-tool setup (`ch-chhound`), sandbox pull, MCP connect, tool names, the symbol-sweep preflight recipe, discovery-only rule
13. `$RAW_BASE/kernel/references/evidence-format.md`
14. `$RAW_BASE/kernel/references/chunker.md` — the shipped Phase-0 unit chunker (CLI/IO, recipe, limits)

### Pi driver (notebook + handoff + model-groups binding — only if this runtime provides the pi notebook)

15. `$RAW_BASE/libs/pi-driver/SKILL.md`
16. `$RAW_BASE/libs/pi-driver/references/requirements-check.md`
17. `$RAW_BASE/libs/pi-driver/references/notebook-plan-contract.md`

### Templates / assets (keep for reference during the episode)

18. `$RAW_BASE/templates/KICKOFF.md`
19. `$RAW_BASE/assets/finding-schema.json`
20. `$RAW_BASE/assets/child-pass-prompt-template.md`

### Worked example (optional, read after compiling the process)

21. `$RAW_BASE/docs/example-review.md`

## Fetching rules

- Use `curl -sL <url>` or an equivalent raw-download tool.
- Do **not** summarize, paraphrase, or truncate. The kernel text is normative.
- Hold the fetched text in a scratch location you can re-read during the session.
- Report `file: <line-count>` for every file before proceeding.
- The Phase-0 chunker executable at `$RAW_BASE/kernel/tools/chunker.mjs` must be fetched as exact raw bytes (never markdown-normalized) and its sha256 recorded at fetch time before the Phase-0 run (remote-boot source-OID binding for the executable remains an explicit checkpoint).

## After fetching

1. Run the **quick requirements check** (pi-driver `requirements-check.md`) — pre-pull rows only; the subject-tree rows (5/8/9) defer to the Phase 0 gate, where the check completes.
2. Ask the **intake fields once** (from `KICKOFF.md` — see below for the field list).
3. Compile the run frame (frozen options + planned subject mechanism — no tree fields yet; held unsealed) and show the compiled frame with the requirements-check result to the operator.
4. **Wait for the operator's explicit frame confirmation.** Do not write, read back or seal before it.
5. On confirmation, write the frame page + findings skeleton and read both back (notebook-plan-contract.md), then — if `handoff` is available in this runtime — seal the compiled frame and hand off so the next context starts from the sealed compile, pulls the subject (the first tree read — no local target checkout is read before it), records `subject_path` / `subject_oid` at the Phase 0 gate, and runs **Phase 0 → Vector 1**. Else continue in-session.

## Bootstrap prompt (paste into a fresh session)

> Boot a cure-light PR review episode from the remote manifest at
> `https://raw.githubusercontent.com/grzegorznowak/cure-light/main/BOOTSTRAP.md`
> Fetch the manifest, then follow its instructions exactly: fetch the listed
> files as raw markdown (no summarization, preserve bytes), report each file's
> line count, run the quick requirements check, ask the intake fields once
> (owner/repo, PR number, vectors, auto-draft policy — from KICKOFF.md), compile
> the run plan unsealed and show the compiled frame (with the requirements
> result) for explicit confirmation, wait for that confirmation, then write +
> read back the frame and findings skeleton and — because this runtime provides
> the pi notebook + handoff — seal the compiled frame and hand off so the next
> context kicks off Phase 0 (pull subject + contract) then Vector 1. No clone
> or install.