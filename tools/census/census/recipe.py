"""Pinned census recipe + the ``tool-unit/1`` manifest.

Everything in this module is the *pinned* recipe: flags are recorded in the
artifact and must never vary silently.  ``census check`` recomputes with these
constants, not with anything read from the artifact file.
"""

from __future__ import annotations

from toolkit import tool_unit

TOOL_NAME = "census"
TOOL_VERSION = "0.1.0"

SCHEMA_VERSION = "changed-range-census/1"

RECIPE_VERSION = "1"
DIFF_ALGORITHM = "myers"
CONTEXT = 0
NO_RENAMES = True

#: ``-c`` config args present on every diff invocation (path parsing + submodule
#: events must be deterministic regardless of user config).
CONFIG_ARGS = ("-c", "core.quotePath=false")

PATCH_FLAGS = (
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--diff-algorithm=myers",
    "--no-indent-heuristic",
    "--no-renames",
    "--ignore-submodules=none",
    "-U0",
)
NAME_STATUS_FLAGS = (
    "--no-ext-diff",
    "--no-textconv",
    "--name-status",
    "-z",
    "--no-renames",
    "--ignore-submodules=none",
)
NUMSTAT_FLAGS = (
    "--no-ext-diff",
    "--no-textconv",
    "--numstat",
    "-z",
    "--no-renames",
    "--ignore-submodules=none",
)
STAT_FLAGS = (
    "--no-ext-diff",
    "--no-textconv",
    "--stat",
    "--no-renames",
    "--ignore-submodules=none",
)

#: Verbatim flag strings recorded in ``recipe.flags`` (one per invocation).
FLAG_STRINGS = (
    "-c core.quotePath=false diff " + " ".join(PATCH_FLAGS),
    "-c core.quotePath=false diff " + " ".join(NAME_STATUS_FLAGS),
    "-c core.quotePath=false diff " + " ".join(NUMSTAT_FLAGS),
    "-c core.quotePath=false diff " + " ".join(STAT_FLAGS),
)


def build_recipe(git_version: str) -> dict:
    """The canonical ``recipe`` object for this run (git version is part of it)."""
    return {
        "version": RECIPE_VERSION,
        "git_version": git_version,
        "flags": list(FLAG_STRINGS),
        "diff_algorithm": DIFF_ALGORITHM,
        "no_renames": NO_RENAMES,
        "context": CONTEXT,
    }


def manifest() -> dict:
    """The static ``tool-unit/1`` describe manifest (no timestamps/paths)."""
    run_usage = (
        "census run --repo PATH --base REF --subject REF --out CENSUS.json "
        "[--scratch DIR]"
    )
    check_usage = "census check --census CENSUS.json --repo PATH [--scratch DIR]"
    return tool_unit.build_manifest(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        summary=(
            "Deterministic changed-range census (changed-range-census/1) over "
            "base..subject with a pinned two-dot git-diff recipe; parents are "
            "-U0 edit blocks, metadata changes are events, and every stream is "
            "reconciled in a partition check"
        ),
        dependencies=[],
        commands={
            "run": {
                "usage": run_usage,
                "summary": (
                    "Run the pinned two-dot diff recipe and write the canonical "
                    "changed-range-census/1 artifact"
                ),
                "params": [
                    {
                        "name": "--repo",
                        "type": "path",
                        "required": True,
                        "default": None,
                        "description": "subject git repository (read-only; scratch must be outside it)",
                    },
                    {
                        "name": "--base",
                        "type": "string",
                        "required": True,
                        "default": None,
                        "description": "base ref; resolved with git rev-parse --verify <ref>^{commit}",
                    },
                    {
                        "name": "--subject",
                        "type": "string",
                        "required": True,
                        "default": None,
                        "description": "subject ref; resolved with git rev-parse --verify <ref>^{commit}",
                    },
                    {
                        "name": "--out",
                        "type": "path",
                        "required": True,
                        "default": None,
                        "description": "canonical changed-range-census/1 JSON output path (no trailing newline)",
                    },
                    {
                        "name": "--scratch",
                        "type": "path",
                        "required": False,
                        "default": None,
                        "description": "raw stream scratch dir (default: fresh temp dir outside the repo)",
                    },
                ],
                "outputs": {
                    "--out": "changed-range-census/1 canonical JSON, no trailing newline",
                    "stdout": "JSON summary with census_hash, counts, partition.ok, out and scratch",
                },
                "exit_codes": {
                    "0": "ok; partition.ok is true",
                    "1": "extraction/partition failure; artifact written with partition.ok=false and actionable errors",
                    "2": "usage or environment (missing git, bad repo/ref, scratch inside the repo)",
                },
            },
            "check": {
                "usage": check_usage,
                "summary": (
                    "Recompute the census in a fresh temp scratch with the pinned "
                    "recipe and compare census_hash (canonical payload minus the "
                    "environment-varying identity observations), counts and "
                    "partition; repo OIDs must still resolve and the git version "
                    "must match"
                ),
                "params": [
                    {
                        "name": "--census",
                        "type": "path",
                        "required": True,
                        "default": None,
                        "description": "changed-range-census/1 artifact to verify (canonical bytes required)",
                    },
                    {
                        "name": "--repo",
                        "type": "path",
                        "required": True,
                        "default": None,
                        "description": "git repository holding the recorded OIDs (read-only)",
                    },
                    {
                        "name": "--scratch",
                        "type": "path",
                        "required": False,
                        "default": None,
                        "description": "parent dir for the fresh check scratch (default: system temp)",
                    },
                ],
                "outputs": {
                    "stdout": "census-check/1 JSON report with per-check {id, ok, detail}, errors, census_hash, recomputed_census_hash and an informational observations block (declared vs current repo/head_oid/worktree_dirty)",
                },
                "exit_codes": {
                    "0": "all checks ok; recomputed census_hash matches",
                    "1": "verification failure; report.errors name the failing check",
                    "2": "usage or environment (missing git, bad repo, unreadable artifact)",
                },
            },
        },
        recipe_pins={
            "changed-range-census": SCHEMA_VERSION,
            "diff": (
                "git -C repo -c core.quotePath=false diff " + " ".join(PATCH_FLAGS)
                + " <base_oid>..<subject_oid>"
            ),
            "name-status": (
                "git -C repo -c core.quotePath=false diff "
                + " ".join(NAME_STATUS_FLAGS)
                + " <base_oid>..<subject_oid>"
            ),
            "numstat": (
                "git -C repo -c core.quotePath=false diff "
                + " ".join(NUMSTAT_FLAGS)
                + " <base_oid>..<subject_oid>"
            ),
            "stat": (
                "git -C repo -c core.quotePath=false diff "
                + " ".join(STAT_FLAGS)
                + " <base_oid>..<subject_oid>  # orientation only, never the denominator"
            ),
        },
        determinism={
            "idempotent": True,
            "no_hidden_state": True,
            "identical_inputs_to_identical_outputs": True,
            "notes": (
                "census_hash binds base/subject OIDs, refs, recipe, files, parents, "
                "events, counts and partition and is identical for the same repo "
                "state and git version; the environment-varying identity "
                "observations (repo path, HEAD, worktree dirtiness) are recorded "
                "for audit but excluded from the hash"
            ),
        },
    )
