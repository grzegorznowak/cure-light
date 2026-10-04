// RED-first docs/identity-chain contract tests for the pinned verifier P5
// phase (plan §4 batch E / §5 items 1–12). They assert that the operator-facing
// docs carry the verifier identity chain + delegation contract, and that stale
// "chunker-only / not a shipped gate tool" exclusivity is gone. These tests
// were authored BEFORE the docs edits (the intended failure mode is a missing
// clause, not a crash). Run with:
//
//   node --test kernel/tools/verify.docs.test.mjs
//
// The tool invocation pointer lives ONLY in kernel/tools/verify.mjs's header;
// no operator-facing doc may carry a suite pointer (asserted below).
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (rel) => readFileSync(path.join(ROOT, rel), "utf8");
const norm = (s) => s.replace(/\s+/g, " ").trim();

const CHILD_TEMPLATE = "assets/child-pass-prompt-template.md";
const INTAKE = "kernel/references/intake-and-scope.md";
const CONFORMANCE = "kernel/references/conformance-pass.md";
const REQUIREMENTS = "libs/pi-driver/references/requirements-check.md";
const KICKOFF = "templates/KICKOFF.md";
const BOOTSTRAP = "BOOTSTRAP.md";
const SKILL = "kernel/SKILL.md";
const NOTEBOOK_CONTRACT = "libs/pi-driver/references/notebook-plan-contract.md";
const README = "README.md";
const CHANGELOG = "CHANGELOG.md";
const CHUNKER = "kernel/references/chunker.md";
const EVIDENCE = "kernel/references/evidence-format.md";
const VALIDATION_PLAN = "docs/contract-adequacy-validation-plan.md";
const PIPELINE = "kernel/references/pipeline-model.md";

function has(file, snippet, label) {
  const body = norm(read(file));
  assert.ok(
    body.includes(norm(snippet)),
    `${file}: missing ${label}\n  wanted: ${norm(snippet)}`,
  );
}

function lacks(file, re, label) {
  const body = read(file);
  assert.doesNotMatch(body, re, `${file}: stale ${label} still present`);
}

function row(text, prefix) {
  const line = text.split("\n").find((l) => l.startsWith(prefix));
  assert.ok(line, `missing table row ${prefix}`);
  return line;
}

describe("docs contract — child prompt template (verifier block)", () => {
  it("carries the mechanical verification child block", () => {
    has(CHILD_TEMPLATE, "### Mechanical verification child (`fast`; not a reviewer)", "verifier block heading");
  });

  it("mandates a fast child, read-only with no interpret/repair, and hash verification", () => {
    has(CHILD_TEMPLATE, "MUST spawn a `fast` child", "fast-child mandate");
    has(CHILD_TEMPLATE, "verifies the frame-recorded `{verifier_path}` / `{verifier_sha256}`", "recorded path/sha verification");
    has(CHILD_TEMPLATE, "do not interpret, repair or normalize", "read-only no-interpret clause");
    has(CHILD_TEMPLATE, "do not substitute checks", "no-check-substitution clause");
    has(CHILD_TEMPLATE, "Missing/degenerate `fast` pauses; no coordinator fallback", "pause, no fallback clause");
    has(CHILD_TEMPLATE, "must NOT read the subject", "no-subject-read clause");
  });

  it("fails the mechanical gate on nonzero, mismatch, missing or inconsistent verdicts", () => {
    has(
      CHILD_TEMPLATE,
      "A nonzero exit, a missing or unparseable verdict, a truncated return, a tool/hash mismatch, or an ok/exit inconsistency fails this mechanical gate",
      "mechanical-gate failure clause",
    );
  });

  it("coordinator consumes the verdict and never re-implements; semantics stay coordinator/V1", () => {
    has(
      CHILD_TEMPLATE,
      "The coordinator consumes the verdict; it never overrides, reimplements or reruns checks in its own context",
      "consume-only clause",
    );
    has(
      CHILD_TEMPLATE,
      "dispositions remain coordinator/V1 semantic work",
      "semantic-disposition clause",
    );
  });

  it("declares the five frame slots", () => {
    for (const slot of ["{verifier_command}", "{verifier_path}", "{verifier_sha256}", "{run_root}", "{artifact_class}"]) {
      has(CHILD_TEMPLATE, slot, `slot ${slot}`);
    }
  });

  it("aligns the P0.2 draft shape with the frozen claims profile", () => {
    has(CHILD_TEMPLATE, "sources[{source_ref,locator,path,role,sha256,byte_length[,blob_subject]}]", "sources profile");
    has(CHILD_TEMPLATE, "claims[{id,statement,source_ref,quote,also_in}]", "claims profile");
    has(CHILD_TEMPLATE, "nonclaims[{id,statement,source_ref,quote,reason}]", "nonclaims profile");
    has(CHILD_TEMPLATE, "conflicts[{id,kind,materiality,quotes[{source_ref,quote,offset_bytes}]", "conflicts profile");
    has(CHILD_TEMPLATE, "notes[{note}]", "notes profile");
    has(CHILD_TEMPLATE, "missing_source_candidates[{resource,affected_claim_ids,reference_quote,why_it_matters}]", "candidates profile");
  });

  it("uses the separate P0.4 removes/changes role tokens", () => {
    has(CHILD_TEMPLATE, "necessary-support | removes | changes", "separate removes/changes tokens");
    lacks(CHILD_TEMPLATE, /remove[s]?\/changes/, "slash-drift removes/changes token");
  });

  it("retains original worker attempts", () => {
    has(CHILD_TEMPLATE, "Retain the original worker attempts", "original-attempts clause");
  });
});

describe("docs contract — intake-and-scope (P0 delegation + pinned verifier)", () => {
  it("delegates verify claims/units/join at the P0 stages", () => {
    has(INTAKE, "verify claims", "delegated verify claims");
    has(INTAKE, "verify units", "delegated verify units");
    has(INTAKE, "verify join", "delegated verify join");
  });

  it("flows P0.5 as the coordinator semantic gate consuming the fast-child pinned verdict", () => {
    has(INTAKE, "P0.5 coordinator semantic gate", "P0.5 semantic-gate line");
    has(INTAKE, "consumes the fast-child pinned mechanical verdict", "verdict-consumption line");
  });

  it("replaces 'not a shipped gate tool' with shipped mechanical checks + coordinator merge decision", () => {
    lacks(INTAKE, /not a shipped gate tool/i, "not-a-shipped-gate-tool phrasing");
    has(INTAKE, "mechanical checks shipped in `kernel/tools/verify.mjs`", "shipped mechanical checks");
    has(INTAKE, "merge decision remains coordinator", "coordinator merge decision");
  });

  it("documents the pinned-verifier CLI, exit codes, fail-closed semantics and envelope", () => {
    has(INTAKE, "### Pinned mechanical verifier (`kernel/tools/verify.mjs`)", "verifier subsection");
    has(INTAKE, "node <pinned-engine>/kernel/tools/verify.mjs <claims|units|join> --run <run-root>", "CLI invocation");
    has(INTAKE, "Exactly one `--run`", "single --run rule");
    has(INTAKE, "Exit codes: 0 pass / 1 validation failure / 2 usage-or-unknown-schema refusal", "exit-code contract");
    has(INTAKE, "Nonzero is mechanically binding", "binding nonzero");
    has(INTAKE, "Fail-closed delegation", "fail-closed semantics");
    has(INTAKE, "run-verification/1", "envelope schema");
    has(INTAKE, "each command requires only its own evidence slice", "stage-scoped evidence");
    has(INTAKE, "never reads the subject tree", "read boundary");
  });

  it("documents the enforced floor(n/2) halves geometry (F5)", () => {
    has(INTAKE, "left = floor(n/2) units", "floor-left rule");
    has(INTAKE, "right larger for odd n", "right-larger rule");
    has(INTAKE, "no unit split", "no-unit-split rule");
    lacks(INTAKE, /exact half-split point stays coordinator policy/, "coordinator-policy half-split drift");
  });

  it("documents check suppression semantics (F11)", () => {
    has(INTAKE, "**Check suppression.**", "suppression heading");
    has(INTAKE, "Absence means NOT EVALUATED", "absence-not-evaluated");
    has(INTAKE, "can never be read as a pass", "absence-not-pass");
    has(INTAKE, "Duplicate JSON object keys", "duplicate-key limitation note");
  });

  it("documents the payload-walk boundary (F16)", () => {
    has(INTAKE, "The payload walk does not traverse symlinked directories", "payload-walk symlink-dir rule");
    has(INTAKE, "payload files must be regular files inside the run root (outside-root targets refuse)", "payload regular-file/inside-root rule");
  });

  it("marks ledger/findings/closure validators NOT IMPLEMENTED with no CLI placeholder", () => {
    has(INTAKE, "NOT IMPLEMENTED", "not-implemented marker");
    has(INTAKE, "no CLI placeholder", "no-placeholder clause");
  });

  it("requires three current verdict refs/hashes/codes in the gate checklist", () => {
    has(INTAKE, "current delegated `verify claims|units|join` verdicts", "current delegated verdicts");
    has(INTAKE, "(ref, sha256, exit code)", "verdict ref/hash/code shape");
  });

  it("adds the verifier pin, verdict records, envelope ref/hash and approved policy to the output manifest", () => {
    has(INTAKE, "verifier: {path: kernel/tools/verify.mjs, sha256, tool_version: 1.0.0}", "verifier pin line");
    has(INTAKE, "verification: {claims: {ref, sha256, exit_code}", "verification record line");
    has(INTAKE, "run_envelope: {ref: run-manifest.json, sha256, schema_version: run-verification/1}", "envelope line");
    has(INTAKE, "pilot: {operator_ref, input_ceiling_bytes, witness_max_chars: 160", "pilot policy line");
  });
});

describe("docs contract — conformance-pass (V1 mechanical boundary)", () => {
  it("requires current delegated verdicts pinned to exact inputs; stale/nonzero stops the boundary", () => {
    has(CONFORMANCE, "current delegated `fast`-child verdicts", "current delegated verdicts");
    has(CONFORMANCE, "verdict stops the mechanical boundary", "stale/nonzero stop");
    has(CONFORMANCE, "never re-implements or reruns the tool's checks in its own context", "no-reimplementation clause");
  });

  it("reuses Phase-0 verify commands against preserved refs, not claims-frozen under draft schema", () => {
    has(CONFORMANCE, "reuse the Phase-0 `verify claims|units|join` surface", "phase-0 reuse");
    has(CONFORMANCE, "never fed to the draft-schema validator", "frozen-directory separation");
  });

  it("marks ledger/findings/closure validators NOT IMPLEMENTED at reconciliation point 6", () => {
    has(CONFORMANCE, "ledger, findings and closure", "registry seam subjects");
    has(CONFORMANCE, "NOT IMPLEMENTED", "not-implemented marker");
    has(CONFORMANCE, "no `verify ledger|findings|closure` CLI placeholder", "no CLI placeholder");
  });
});

describe("docs contract — requirements-check (row 10 + groups)", () => {
  it("binds the verifier path/sha256/tool_version in row 10 (engine OID)", () => {
    const text = read(REQUIREMENTS);
    const r10 = row(text, "| 10 |");
    assert.match(r10, /verify\.mjs/, "row 10 must name the verifier");
    assert.match(r10, /sha256/, "row 10 must bind exact bytes");
    assert.match(r10, /tool_version/, "row 10 must bind tool_version");
    assert.match(r10, /engine source|source identity|engine OID/i, "row 10 must bind the engine source identity");
  });

  it("includes the fast mechanical executor in row 7", () => {
    const text = read(REQUIREMENTS);
    const r7 = row(text, "| 7 |");
    assert.match(r7, /mechanical/i, "row 7 must cover the mechanical verification child");
    assert.match(r7, /fast/, "row 7 must remain fast-bound");
  });

  it("stops the mechanical gate on missing verifier/mismatch and forbids run-authored substitutes", () => {
    has(REQUIREMENTS, "Missing verifier", "missing-verifier stop");
    has(REQUIREMENTS, "run-authored verification script", "no run-authored substitute");
  });
});

describe("docs contract — KICKOFF / BOOTSTRAP / SKILL / notebook contract", () => {
  it("KICKOFF §8 carries verifier identity, delegated verification and the semantic-gate framing", () => {
    has(KICKOFF, "pinned mechanical verifier", "verifier identity");
    has(KICKOFF, "tool_version", "tool_version");
    has(KICKOFF, "delegated `fast` mechanical verification", "delegated verification");
    has(KICKOFF, "not a second semantic gate", "not-a-second-semantic-gate");
    has(KICKOFF, "never convert bytes to tokens", "byte-vs-token policy");
    has(KICKOFF, "Phase-0 claims, join and mechanical verification: `fast` only", "fast group covers verification");
  });

  it("BOOTSTRAP fetches the verifier as exact raw bytes with sha recorded at fetch from the immutable source", () => {
    has(BOOTSTRAP, "pinned mechanical verifier `$RAW_BASE/kernel/tools/verify.mjs`", "verifier fetch");
    has(BOOTSTRAP, "fetched as exact raw bytes", "exact raw bytes");
    has(BOOTSTRAP, "recorded at fetch time", "sha at fetch");
    has(BOOTSTRAP, "immutable resolved `cure_light_source_head_oid`", "immutable resolved source");
    has(BOOTSTRAP, "does not by itself prove the OID", "no false OID proof");
    has(BOOTSTRAP, "stop the executable gate", "stop clause");
  });

  it("kernel/SKILL carries the verifier pin, literal contract, phase order and no-override rule", () => {
    has(SKILL, "pinned mechanical verifier", "verifier in requirements");
    has(SKILL, "literal rendered verifier-child contract", "literal delegation contract");
    has(SKILL, "delegated verify claims", "phase-order claims");
    has(SKILL, "delegated verify units", "phase-order units");
    has(SKILL, "delegated verify join", "phase-order join");
    has(SKILL, "never re-implements or reruns the verifier's checks", "no-override rule");
    has(SKILL, "no subject read", "no subject read");
  });

  it("notebook-plan-contract freezes the pin + literal contract and stores verdict bytes/code", () => {
    has(NOTEBOOK_CONTRACT, "verifier path/sha256/tool_version", "frame verifier pin");
    has(NOTEBOOK_CONTRACT, "literal delegated verification-child contract", "literal delegation contract");
    has(NOTEBOOK_CONTRACT, "current per-command fast-child verdict refs/hashes/exit codes", "verdict evidence bind");
    has(NOTEBOOK_CONTRACT, "freezes the verifier pin", "seal freeze");
  });
});

describe("docs contract — README / CHANGELOG / consistency", () => {
  it("README layout mentions kernel/tools/verify.mjs as the pinned mechanical verifier", () => {
    has(README, "tools/verify.mjs", "layout verifier branch");
    has(README, "pinned mechanical verifier", "layout verifier label");
    has(README, "kernel/tools/verify.mjs", "explicit verifier path");
  });

  it("README does not absorb the pending F1/F2 items or a suite pointer", () => {
    lacks(README, /chunker\.mjs/, "F2 chunker listing");
    lacks(README, /Node 22/, "F1 requirements-summary sentence");
    lacks(README, /node --test|verify\.test\.mjs|verify-fixtures/, "test-suite pointer");
  });

  it("CHANGELOG appends a new Unreleased verifier subsection without rewriting history", () => {
    has(CHANGELOG, "### 2026-10-04 — pinned mechanical verifier (claims | units | join)", "new subsection");
    has(CHANGELOG, "kernel/tools/verify.mjs", "verifier path");
    has(CHANGELOG, "run-verification/1", "envelope schema");
    has(CHANGELOG, "fast", "fast delegation");
    has(CHANGELOG, "left = floor(n/2)", "changelog halves geometry");
    lacks(CHANGELOG, /exact half-split point remains coordinator policy/, "changelog half-split drift");
    assert.match(read(CHANGELOG), /NOT IMPLEMENTED/, "changelog must mark the follow-up seam");
    const body = read(CHANGELOG);
    const newAt = body.indexOf("### 2026-10-04 — pinned mechanical verifier");
    const oldAt = body.indexOf("### 2026-10-03 — V1 claim-validation boundary");
    assert.ok(newAt !== -1 && oldAt !== -1 && newAt < oldAt, "new subsection must sit above the 2026-10-03 history");
    assert.match(body, /The coordinator gate is not a shipped tool\./, "historical entry must remain as written");
    has(CHANGELOG, "### 2026-10-02 — Phase 0: claims → chunker → join → gate", "historical section intact");
  });

  it("chunker.md and evidence-format.md note verifier consumption without changing chunker schema", () => {
    has(CHUNKER, "consumed mechanically by the delegated `verify units` command", "chunker verify consumption");
    has(CHUNKER, "chunker schema/output is unchanged", "chunker schema unchanged");
    has(EVIDENCE, "delegated `verify claims|units|join` verdict refs/hashes/exit codes", "evidence verdict refs");
  });

  it("no stale chunker-only / no-gate exclusivity remains in current operator docs", () => {
    const files = [
      CHILD_TEMPLATE, INTAKE, CONFORMANCE, REQUIREMENTS, KICKOFF, BOOTSTRAP,
      SKILL, NOTEBOOK_CONTRACT, README, CHUNKER, EVIDENCE, VALIDATION_PLAN, PIPELINE,
    ];
    const stale = [
      [/not a shipped gate tool/i, "not-a-shipped-gate-tool"],
      [/only the chunker/i, "chunker-only exclusivity"],
      [/chunker ships as a tool;\s*no gate/i, "chunker-only no-gate exclusivity"],
      [/not a second shipped tool/i, "not-a-second-shipped-tool"],
    ];
    for (const file of files) {
      for (const [re, label] of stale) lacks(file, re, `${label} in ${file}`);
    }
  });

  it("keeps the tool-invocation pointer out of every operator-facing doc", () => {
    const files = [
      CHILD_TEMPLATE, INTAKE, CONFORMANCE, REQUIREMENTS, KICKOFF, BOOTSTRAP,
      SKILL, NOTEBOOK_CONTRACT, README, CHANGELOG, CHUNKER, EVIDENCE, VALIDATION_PLAN, PIPELINE,
    ];
    for (const file of files) {
      lacks(file, /node --test|verify\.test\.mjs|verify-fixtures/, `suite pointer in ${file}`);
    }
  });
});
