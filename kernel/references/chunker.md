# chunker.md — Phase-0 code units

The chunker is the small zero-dependency engine tool shipped at
[`kernel/tools/chunker.mjs`](../tools/chunker.mjs). It supplies the unit inventory
for P0.4 joining and V1 accounting; it does not extract claims, judge links,
finalize UNCLAIMED or implement the coordinator's P0.5 gate.

## Identity and invocation

The compiled frame records the engine script path, sha256 of its exact bytes,
and recipe, bound to `cure_light_source_head_oid`. Use the script from that
cure-light source, never a copy from the review subject. Run with Node and git;
no package install, parser library, Python environment or census plugin is needed.

```text
node <cure-light>/kernel/tools/chunker.mjs <repo> <base> <subject> <outDir>
  → <outDir>/units2/manifest.json
  → <outDir>/units2/u0000.txt …
```

`repo` is the pulled subject repo; pass the state's frozen `base_oid` and
`subject_oid`, not moving remote names. `outDir` is a fresh run-artifact location
outside the subject. The manifest's `units[].file` paths are relative to this
root. Missing positional arguments exit 2; a failed git/read/write or an
indivisible over-ceiling line exits non-zero and never publishes a manifest —
a failed chunking step is never an empty successful inventory. Stdout reports
counts and one compact line per unit; consumers use artifact paths, and a
failure never counts as coverage of the changed surface.

## Recipe

Use two-dot `base..subject`, not a merge-base substitution:

```text
git -C <repo> -c core.quotepath=false diff -U3 --no-ext-diff --no-color \
    --no-renames --no-textconv --diff-algorithm=myers <base>..<subject>
```

`--no-textconv` and `--no-ext-diff` keep subject-configured diff filters (which
are subject-tree executables) out of the run; `core.quotepath=false` keeps paths
stable. Partition in diff file order into windows, target 4096 bytes / ceiling
6144 bytes. Prefer file-end → hunk-end → block-end → line-end, never mid-line.
Whole hunks fit together when within the ceiling; oversized hunks are grouped at
logical block boundaries before line fallback. Block detection is a lexical
heuristic: definition-start lines (`def`, `class`, `function`, `export`, etc.),
otherwise blank-line paragraphs — not AST ownership. Units never cross files.
P0.4 packs whole units in manifest order and never splits a unit between children.

An indivisible line larger than the ceiling cannot satisfy both bounds: the
chunker fails that step rather than splitting mid-line or claiming a bounded
result. No-hunk file metadata remains visible as a `file` unit, not silently
excluded; metadata units are not code windows and are exempt from the window
ceiling. Determinism means identical frozen inputs and effective diff recipe
produce the same ordered units; model-authored claims/links do not share this
guarantee.

## Manifest and payload contract

The emitted manifest is `code-units-sim/2` (the schema name carried over from the
reference simulation; a production rename is an explicit checkpoint, not a silent
change). It records `recipe`, `identity`, `counts` and ordered `units`.
`recipe` records chunker name, target/ceiling bytes, context and block preference.
`identity` records repo, input refs and resolved base/subject OIDs. `counts`
records units, diff files, line-split units and total stored bytes. Each unit
records `unit_id`, relative `file`, target `path`, `ranges`, `hunk_count`,
`byte_len`, `blocks` and `boundary_kind` (`file`, `block`, `line-split`).
Ranges contain old/new start/count pairs from contributing hunk headers. Unit IDs
are sequential and state-bound, not globally canonical identities.

Payloads are diff fragments with context. `byte_len` is the exact stored payload
size (`lines.join("\n")`, no trailing newline) and matches the payload file. Hunk
ranges can repeat across units; `hunk_count` is the number of recorded range
entries, not necessarily distinct hunks. Neither context lengths nor repeated
ranges are unique changed-line counts. `blocks` is a grouping counter (whole
hunks count 1; split logical blocks increment), not an AST count.

The script emits no SHA fields, engine OID or self-verification; the coordinator
wrapper records path + sha256 + recipe at `cure_light_source_head_oid` and binds
manifest/payload bytes to retained run evidence.

## Validation and limits

Verify the manifest resolves to this state's OIDs and every referenced payload
exists; verify all diff file surfaces are represented, order is preserved,
payloads are within bounds (or the step failed), and replay under the same frozen
inputs and effective recipe is identical. Unknown or unrepresented surfaces remain
explicit limitations; they never become complete coverage or a speculative
negative.

Port deltas over the reference simulation, already applied in the shipped script:
exact payload byte measure; buffered emission preserves diff order; `line-split`
does not stick past the buffer that produced it; `--no-textconv` /
`core.quotepath=false` hardening; an over-ceiling indivisible line is a hard
error. Remaining limits: paths that are not valid UTF-8 may be mangled by text
decoding; a path git still C-quotes (embedded quotes, backslashes or control
characters) is stored as the raw header text rather than a decoded path;
splitting can repeat a hunk's full range in several units, so ranges are not a
disjoint line denominator; and runner-specific git configuration beyond the
explicit flags above is not asserted. These are port-validation checkpoints, not
permissions to import the retired changed-line census semantics.

The coordinator checks join completeness under
[intake-and-scope.md](intake-and-scope.md) §0.3; only V1 finalizes accounting under
[conformance-pass.md](conformance-pass.md).
