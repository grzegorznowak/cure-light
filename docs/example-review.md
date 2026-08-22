# example-review.md — a worked run (PR #27, agenticoding/pi-agenticoding)

A condensed walk-through of a real cure-light-style review, to imitate rather than re-read. The PR added model-modality awareness to a spawn system; the review ran the full pipeline against a moving head.

## The run manifest (condensed)

```text
owner/repo: agenticoding/pi-agenticoding
pr: 27   head f6a4615 → … → 0091fdc (moved 4× mid-review)
vectors: [conformance, implementation, debt]
groups: {conformance: flash, implementation: code-review, debt: code-review}
contract: PR description + issue #26 (bullets + tech context + LOCKED decisions Q1/Q2)
```

Keep this manifest; the closure loop needs the head OID you reviewed, not the branch tip.

## Vector 1 — conformance (flash × 5)

Split by contract surface: derivation core · persistence/schema guard · spawn/router gate · main-session+TUI · tests. RAW results:

- **GAP A1**: v1 config with a *malformed* override crashed load (TypeError) — fixed by comma `cc03b1d` (validateOverride for all versions).
- **GAP A2**: PR said "unsupported additions rejected" but read-path silently capped; write-path only.
- **GAP B-series**: TUI editor commit path, CRUD-gate rejection, boot-notify counts, tool-level forwarding all untested despite claims.
- Confirmed-conformant: derivation algebra, read-time no-download, version guard 3-layer, fail-early before child session, prompt injection format, console hygiene.

## Vector 2 — implementation bugs (code-review × 5)

Split by sealed invariant: derivation edge cases · store durability/security · spawn lifecycle/reachability · orchestration escaping · test integrity.
**Origin segmentation (base-diff)**:
- **Pre-existing → issue #27 hardening ticket**: no fsync, no lock/CAS, symlink path resolution, `saveModelGroups` overwriting corrupt files without backup. All present at base `4efc9cf`.
- **PR-introduced → PR comment**: v1 valid-override version-gate regression; `requiredModalities` rejection untested at the public seam; TUI editor coverage; low-level save bypassing the cap.

Closure loop (implementer "addressed"): head moved → delta review → E1/E2/E4/E5 verified-fixed; B7/A4 re-classified (documented); **MG-01 re-classified by implementer as "locked" without operator sign-off — flagged but not re-raised per operator**.

## Vector 3 — debt (code-review × 5)

Bigger concepts: pluggability claim · four divergent group semantics · TUI→config projection · store host-coupling · test topology.
- **HIGH — pluggability aspirational**: `model-groups` shipped modalities as a hard-coded vertical slice; issue #26's "pluggable" extension (min-context/price) would require ~10 touch points.
- **HIGH — four "what can this group do" consumers** disagree on the same group (auth-aware validation vs auth-blind derivation vs router gate vs boot prompt).
- **MED — projection leak**: TUI cloned a `ResolvedModelGroup` (incl. transient modalities) into the persisted config; the PR's own "opaque-key-lossless" normalization made it persist.

## Dispositions

- **#27 hardening** ∈ `gh issue #28` (pre-existing).
- **in-scope** landed as PR comment; implementer Option C landed a constraint-kernel refactor with a synthetic `testMinContainer` descriptor proving pluggability.
- **deferred (honest)**: auth-aware aggregation, uncached derivation.
- **closed-by-operator**: MG-01 (suppressed, auditable).

## What the worked example teaches

1. The head WILL move mid-review; pin + manifest, gate the fleet.
2. Origin classification (base-diff) decides which findings are the PR's problem vs inherited debt.
3. Closure is delta: unchanged code cannot be green; deferred ≠ fixed.
4. The operator's "don't re-raise X" is a `closed-by-operator` record, not a disappearance.
5. A stated pluggability claim that the code doesn't back is HIGH debt, replaced by genuine abstraction via Option C.

Files referenced are illustrative only; your run recovers them from the target repo.