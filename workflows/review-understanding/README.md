# review-understanding

A small, standalone PR-understanding workflow for [pi](https://pi.dev). Read a pull request from its description, directly linked issues and the code changeset, summarize the cumulative changes by domain, then suggest digestible domain or ticket slices with dependencies and review order. Exactly two serial skill runs; structured output on the first run by default, with `--plain` for comparison.

This package lives in the cure-light repo under `workflows/review-understanding/`, but it is developed and delivered as a standalone unit in the style of `ddd-iteration`: one canonical source, symlink installation into any consuming project, shipped model-group config, headless tests, CI, and MIT licensing. It is separate from the paused review pipeline and does not extend it.

## Dependencies

- **pi host** — the runtime that loads and runs the workflow. Developed against pi v1.4.0; any current 1.x should work, but pin what you validated.
- **pi-schematic plugin** — provides `model-group:` frontmatter routing used by the skills. The running/validated version of the plugin is:
  - `git:github.com/chunkhound/pi-schematic@feat/workflow` — commit `4c68b4f` — version `0.7.0`
  - Install per pi-schematic's own instructions (plugin checkout under the pi agent environment, `git` layout as documented there). Do not rely on an npm-published copy: routing parity is validated against this pinned branch.
- **model-groups config** — the consuming project must define two groups, `code-review` and `plan`, under `.pi/pi-schematic/model-groups.json` (schema v2). A canonical file ships with this package. See **Model-group routing** below.
- **gh CLI and GitHub access** — required for actual PR reads; not needed for the headless tests.
- Node.js 24 is used in CI; the installer and tests use only Node built-ins (no external packages).

## What you get

- A two-run workflow (`review-understanding.js`): understand (skill `review-understanding-summary`) → suggest splits (skill `review-understanding-splits`), with the summary passed explicitly
- Two workflow skills, each with its own `model-group` route and `readonly: true` frontmatter, plus a standalone `check-tests-soundness` skill for reviewing the test surface of a diff
- Structured first output by default (`options.output.schema`), a `--plain` mode with the same skill and research input, and an honest comparison protocol
- A model-group preflight: the workflow fails fast, before any model spend, when `code-review` or `plan` is absent or has no members
- An installer (`install.mjs`) with strict no-overwrite/no-delete preflight, a regular workflow copy and skill symlinks
- A shipped `model-groups.json` (schema v2) with the two required groups
- No external npm dependencies; headless tests in `test/`

## Install into a project

The package is delivered from this repository. From the target project root:

```bash
cd /path/to/your/project
node /path/to/cure-light/workflows/review-understanding/install.mjs
```

The current working directory is the project — there is nothing else to decide. Start pi from this directory and reload resources after installation. The installer writes:

- `.pi/workflows/review-understanding.js` → regular copy of canonical `review-understanding.js`
- `.pi/skills/review-understanding-summary` → symlink to canonical skill directory
- `.pi/skills/review-understanding-splits` → symlink to canonical skill directory
- `.pi/skills/check-tests-soundness` → symlink to canonical skill directory

The workflow is a regular copy (not a symlink) so it appears in the `/workflows` TUI list; the host's list ignores symlinked `.js` files, though bare-name resolution would still work. Skills stay symlinks — the skill loader follows them — so skill edits propagate from the canonical source. Rerunning the installer also links skills added since the first install. A previously installed correct symlink (from older installer versions) is upgraded to the copy automatically on rerun. If you change the canonical workflow, rerun the installer after removing the old `.pi/workflows/review-understanding.js` copy (an identical copy rerun reports `existing`; a different copy is a refused conflict). Run `node install.mjs --help` for flags; `--dry-run` checks everything without writing; rerunning is safe and idempotent.

This repository ships `code-review` and `plan` with default single members at `.pi/pi-schematic/model-groups.json` — starting pi from the cure-light root already satisfies the preflight. For any other project, bring the groups config there (once per project):

```bash
mkdir -p .pi/pi-schematic
cp /path/to/cure-light/workflows/review-understanding/.pi/pi-schematic/model-groups.json .pi/pi-schematic/model-groups.json
```

Then edit `.pi/pi-schematic/model-groups.json` if you want different members (see below). Reload pi resources after changes.

## Run the workflow

From the installed project root:

```text
/workflow review-understanding https://github.com/OWNER/REPO/pull/123
/workflow review-understanding https://github.com/OWNER/REPO/pull/123 --plain
```

The argument is one GitHub.com PR URL, optionally followed by `--plain` (structured output off for the first run only). The summary skill reads the PR description, linked issues and full diff via read-only `gh`, then returns a structured domain summary. The splits skill receives that summary and returns Markdown suggestions. Results are kept in checkpoint/exit metadata: `pr_url`, `format`, `understanding`, `splits`. `reason: ok` means both calls returned — **not** that evidence is complete or the PR is approved.

To run directly from the canonical source (cure-light root) instead of an installed project link:

```text
/workflow ./workflows/review-understanding/review-understanding.js https://github.com/OWNER/REPO/pull/123
```

The skills must be discoverable from that working directory: run the installer there (links them into `.pi/skills/`) or register them in your agent skills directory.

## Model-group routing

Each skill selects its group via `model-group:` frontmatter. The canonical project-scoped groups ship with this package at `.pi/pi-schematic/model-groups.json` (schema v2). A consuming project copies that file into its own `.pi/pi-schematic/model-groups.json` and fills in members.

| Group | Member(s) | Provider | Thinking |
|---|---|---|---|
| `code-review` | *(configure one)* | *(your provider)* | *(your choice)* |
| `plan` | *(configure one)* | *(your provider)* | *(your choice)* |

The shipped groups carry one default member each; consumers may edit the copy (models/thinking are project policy) or replace members with ones valid on their machine. A missing file means no groups; a selector referencing an unknown or empty group blocks the turn. Use single-member groups for deterministic selection; for an accuracy comparison, pin the same concrete member in every session.

**The workflow enforces this.** Before any model run it checks the project and global model-groups config and exits `needs-input` when `code-review` or `plan` is missing or has zero members, listing the missing/empty groups and a fix hint. This applies to both `structured` and `--plain`. For hermetic operation and tests the check honors `REVIEW_UNDERSTANDING_PROJECT_GROUPS` and `REVIEW_UNDERSTANDING_GLOBAL_GROUPS` (paths to config files) instead of the real defaults.

## Skill runs and safety

Each of the two workflow invocations is a `workflow.run()` call to an explicit skill. The workflow enables readonly for both runs and restores the prior posture after ordinary completion or errors; a terminal budget stop or cancellation can leave readonly enabled, so check the session posture before continuing. The standalone `check-tests-soundness` skill is installed alongside them but is not invoked by the workflow; run it directly when needed. Readonly is a guardrail, not a remote-write security boundary; the skills also explicitly require read-only `gh` use and forbid posting, edits, checkouts, project tests and spawned children. PR/issue/diff content is untrusted data, never instructions.

An explicit skill run may include multiple tool or model turns; two `workflow.run` calls are not a promise of exactly two provider requests. Skill frontmatter routing requires a supported UI context; UI-less hosts may not apply group settings, so the explicit readonly guard is retained. The final selected model can remain the `plan` member after completion — skill routing is not an automatic restore of the original model.

## Compare structured output with prose

Append `--plain` to disable structured output on the first call only. Each execution still has two calls; the skill, research args and input stay the same, so only the first output contract changes. Compare separate fresh sessions with the same group configuration, concrete models, settings and unchanged PR base/head; check that source revisions/content stayed constant; repeat before concluding. Check both summaries against the actual PR/issues/diff for domain omissions, invented changes or ticket mappings, evidence accuracy and honest gaps, then compare whether proposed slices preserve dependencies, tests/docs and full scope. A valid schema proves shape, **not factual accuracy**.

## Human operator interface

- Checkpoints after each step expose `phase` (`ready`, `understood`, `split`), `pr_url`, `format`, and the intermediate `understanding`/`splits` so a stop before exit still leaves usable evidence.
- `coverage` (`complete`/`partial`/`blocked`) and `limitations` are carried from the summary into the split step and reported truthfully; partial research is forwarded as partial, never silently upgraded.

## Supported invocation topologies

- **Installed project symlink:** run `node /path/to/cure-light/workflows/review-understanding/install.mjs` from the target project root, then use `/workflow review-understanding <PR-URL>` there.
- **Canonical source:** use `/workflow ./workflows/review-understanding/review-understanding.js <PR-URL>` from the cure-light root; the skills must still be discoverable (run the installer there).

The package is authored and validated for these two topologies. Other launch modes are not validated.

## Development

```bash
cd workflows/review-understanding
node --test test/*.test.mjs   # headless test suite
node install.mjs --dry-run      # installer preflight
```

Optional native checks (no installs, no copied parsers):

- `REVIEW_UNDERSTANDING_SKILL_LOADER=/absolute/pi-coding-agent/dist/core/skills.js node --test test/discovery.test.mjs`
- `REVIEW_UNDERSTANDING_COMPILER=/absolute/pi-schematic/workflow/compile.ts REVIEW_UNDERSTANDING_COMPILER_DEPENDENCIES=/exact/installed/pi-schematic/package.json node --test test/compile.test.mjs`

The contract tests exercise the group preflight with isolated config fixtures; `REVIEW_UNDERSTANDING_PROJECT_GROUPS` / `REVIEW_UNDERSTANDING_GLOBAL_GROUPS` override the real config paths.

CI runs the headless suite and a scratch-project installer dry-run on every push/PR (see `.github/workflows/review-understanding-ci.yml` at the cure-light root).

## License

MIT (see LICENSE).
