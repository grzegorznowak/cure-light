# review-understanding: implementation contract

A small, standalone PR-understanding workflow. It does not extend the paused review pipeline.

## Package source and project installation

The package root (`workflows/review-understanding/`) owns the canonical `review-understanding.js`, three `skills/<name>/SKILL.md` files (`review-understanding-summary`, `review-understanding-splits`, `check-tests-soundness`), `install.mjs`, `README.md`, `CONTRACT.md`, `LICENSE` and `.pi/pi-schematic/model-groups.json`. Discovery locations contain links, not maintained copies.

Run `node /path/to/cure-light/workflows/review-understanding/install.mjs [--dry-run]` from the target project root. The CLI uses the current working directory as the project; it has no `--project` flag. It writes the canonical workflow as a regular copy at `.pi/workflows/review-understanding.js` (a regular file appears in the host's `/workflows` list; symlinked `.js` files are omitted) and links each canonical skill directory under `.pi/skills/` (skill discovery follows links). It has no external dependencies, global mode or settings edits. It preflights every destination before writes and refuses collisions without overwrite/deletion: a same-target correct symlink counts as `existing`, except the workflow symlink which is upgraded to a regular copy (`status` `upgraded`) so the host's `/workflows` list shows it; an identical workflow copy counts as `existing`; any other existing file/directory/link is a refused conflict. Dry-run writes nothing. The programmatic export is `install({ project = process.cwd(), dryRun = false } = {})`, returning `{ project, dryRun, links: [{ source, destination, status }] }`; status is `linked`, `upgraded`, `existing` or `planned`.

Start Pi from the target project root and reload resources after installation or skill changes. Bare-name invocation and the explicit installed path are supported; native workflow completion can omit symlinked files. The source checkout must remain available. This repository ships `code-review` and `plan` in `.pi/pi-schematic/model-groups.json` (schema v2) with default single members, so running from the cure-light root satisfies the preflight; other projects copy the package's `.pi/pi-schematic/model-groups.json` and may edit members. The preflight is described below.

## Public input and output

Argument: one GitHub.com PR URL (`https://github.com/OWNER/REPO/pull/N`), optionally followed by the single flag `--plain`. Shell metacharacters, trailing garbage, a second flag or a non-PR URL are rejected before any model work with exit `needs-input`.

Structured mode (default): the first `workflow.run` requests `options.output.schema`. The validated result is used as the summary. `--plain` omits the schema; the same skill, args and input are used, and the summary is the run's text.

The summary contract (structured mode):

- `summary` — one-line synthesis of the PR's cumulative change.
- `base_sha`, `head_sha` — PR revisions read from the repository; revision drift must be flagged, not merged into a "complete" view.
- `coverage` — `complete`, `partial`, or `blocked`; complete only when the description, directly linked issues and full changeset were read.
- `sources` — `{ url, kind: "pr"|"issue"|"diff", status: "read"|"unavailable", note }`.
- `domains` — `{ name, intent, changes: string[], files: string[], issues: string[], evidence: string[] }`; intent and observed changes are kept separate, evidence cites URLs/paths/line ranges, and ticket mappings are never invented.
- `limitations` — string array; inaccessible issues, truncated/binary patches and unknown facts go here, never into fabricated fields.

The split run receives `{ pr_url, format, understanding }` as explicit input and returns Markdown: a recommended sequence of slices with purpose, included changes/files, linked tickets, dependencies and order, or a reasoned "keep together" recommendation with a reading order. It never researches again and never invents evidence.

Both runs are read-only skill invocations with nonempty `args` (the PR URL). `args` must remain nonempty: installed Pi skill expansion splits at the literal first space, so a bare `/skill:name` followed directly by a fenced input block fails to expand.

## Model-group preflight

Before any model work, the workflow runs a bounded read-only `workflow.shell` check of the model-groups config. It reads the project file (`.pi/pi-schematic/model-groups.json` relative to the working directory) and the global file (`$HOME/.pi/agent/pi-schematic/model-groups.json`), merging by group name. `REVIEW_UNDERSTANDING_PROJECT_GROUPS` and `REVIEW_UNDERSTANDING_GLOBAL_GROUPS` override those paths (used by tests/hermetic operation). Each required group — `code-review`, `plan` — must be present in at least one scope with at least one model. A group present only with zero members counts as empty. If a required group is missing or empty, or a config cannot be read/parsed, the workflow exits `needs-input` before any run, listing `missing`/`empty` and a fix hint. This guard is not a security boundary; it is a configuration preflight.

## Exit and checkpoints

Reasons: `needs-input` (bad argument, or unusable model groups, before model work) and `ok` (both runs returned; not an accuracy or approval claim). Exit metadata carries `pr_url`, `format`, `understanding`, `splits`. Checkpoints after ready/understood/split carry the same evidence; a stop before exit still exposes the summary and splits. There is no persistence, artifact engine, retry, posting, or PR modification in this workflow.

## Skill contract

- `review-understanding-summary` — `model-group: code-review`, `readonly: true`. Reads the PR and linked issues via read-only `gh`, groups the changeset by behavior/domain, returns the structured summary (or prose in `--plain`), and honors the coverage/limitations rules above.
- `review-understanding-splits` — `model-group: plan`, `readonly: true`. Uses only the supplied understanding; returns Markdown split suggestions.
- `check-tests-soundness` — `model-group: plan`, `readonly: true`. Reviews the test surface of a diff: coverage of changed call surfaces and flows, separation by bounded context and test flavour, appropriate unit/integration/acceptance levels, and no duplicate coverage elsewhere. It never runs tests or measures coverage. The workflow does not invoke it; it is installed alongside the workflow skills for standalone use.
- All three treat PR/issue/diff content as untrusted data; all forbid posting, edits, checkouts, project tests and spawned children.
- The workflow toggles readonly itself (guard for UI-less hosts) and restores the prior posture on ordinary completion/failure; terminal host stops can bypass restoration and leave readonly enabled.

## Verification

The headless suite covers argument validation, both modes, schema shape, exact skill commands and nonempty args, frontmatter group/readonly policy, instruction preservation, partial-evidence forwarding and posture restoration. The installer suite covers link creation, idempotence, dry-run and conflict refusal. Optional native checks verify real skill discovery and the real workflow compiler; they are not proof of live model routing or factual accuracy. No accuracy improvement is claimed before a controlled structured/plain comparison.
