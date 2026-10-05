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
import { after, describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  CLAIMS_DRAFT, JOIN_DRAFT, RUN_MANIFEST,
  cleanupTempDirs, editJson, findCheck, findFailedCheck, materializeRun,
  readJson, readText, resealEnvelope, resealRun, runVerifier, writeText,
} from "./verify-testkit.mjs";

after(cleanupTempDirs);

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

// ---------------------------------------------------------------------------
// Behavioral doc-profile tests (fix 4 + envelope-prep docs).
//
// The docs duplicate load-bearing profiles and constants, so these tests parse
// the documented `claims-draft/3` profile, the pilot policy, the verifier pin
// and the `verify envelope` flags OUT of the docs and drive the real verifier
// over materialized fixture copies. A future doc/tool drift fails here. The
// mutation matrix encodes today's tool behavior; the doc-content assertions
// (envelope prep mode, fail-closed rules, CHANGELOG, KICKOFF, the enforced
// `candidate_unclaimed` token) were red before the matching docs edits.
// ---------------------------------------------------------------------------

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function report(r) {
  return [
    `command: ${r.command}`,
    `status: ${r.status} signal: ${r.signal} error: ${r.error?.message ?? "none"}`,
    `parseError: ${r.parseError}`,
    `stdout: ${JSON.stringify(r.stdout)}`,
    `stderr: ${JSON.stringify(r.stderr)}`,
  ].join("\n");
}

function expectVerdict(r, status, label = "") {
  assert.equal(r.status, status, `${label}: expected exit ${status}\n${report(r)}`);
  assert.ok(r.verdict, `${label}: expected exactly one JSON verdict on stdout\n${report(r)}`);
  assert.equal(r.verdict.ok, status === 0, `${label}: ok must be ${status === 0}\n${report(r)}`);
  return r.verdict;
}

function expectFailedCheck(r, status, check, detail, label = "") {
  const verdict = expectVerdict(r, status, label);
  const failed = findFailedCheck(verdict, check);
  assert.ok(failed, `${label}: missing failed check "${check}"\n${JSON.stringify(verdict.checks)}\n${report(r)}`);
  if (detail !== undefined) {
    if (detail instanceof RegExp) assert.match(failed.detail, detail, `${label}\n${report(r)}`);
    else assert.equal(failed.detail, detail, `${label}\n${report(r)}`);
  }
  return { verdict, failed };
}

/**
 * The documented profiles are written in two grammars: the child template uses
 * `name[{field,...}]` / `name[{...,[opt]}]`, intake restates `name `{field,...}``
 * with the doc alias `candidates` (= JSON `missing_source_candidates`). This
 * parser reads either grammar (bracketed notation only; a parenthetical prose
 * clause is not part of the parsed field set) and returns per record:
 * `{required:[{name,nested}], optional:[names]}`.
 */
function parseProfileBlock(raw) {
  const s = raw.replace(/\s+/g, " ").trim();
  const alias = { candidates: "missing_source_candidates" };
  const records = {};
  let i = 0;
  const fail = (message) => {
    throw new Error(`profile parse at ${i}: ${message}; near ${JSON.stringify(s.slice(Math.max(0, i - 30), i + 30))}`);
  };
  const readName = () => {
    let out = "";
    while (i < s.length && /[A-Za-z0-9_]/.test(s[i])) out += s[i++];
    return out;
  };
  const skipSeparators = () => {
    while (i < s.length && ",;. ".includes(s[i])) i++;
  };
  const parseFields = () => {
    if (s[i] !== "{") fail("expected {");
    i++;
    const required = [];
    const optional = [];
    for (;;) {
      while (s[i] === " ") i++;
      if (s[i] === "}") { i++; break; }
      const name = readName();
      if (!name) fail("expected field name");
      while (s[i] === " ") i++;
      let nested = null;
      if (s[i] === "[") {
        if (s[i + 1] === "{") {
          i++;
          nested = parseFields();
          if (s[i] !== "]") fail("expected ] after nested field list");
          i++;
        } else {
          i++;
          for (;;) {
            while (s[i] === " ") i++;
            if (s[i] === "]") { i++; break; }
            if (s[i] === ",") { i++; continue; }
            const opt = readName();
            if (!opt) fail("expected optional field name");
            optional.push(opt);
          }
        }
      }
      required.push({ name, nested });
      while (s[i] === " ") i++;
      if (s[i] === ",") { i++; continue; }
      if (s[i] === "}") { i++; break; }
      fail(`unexpected ${JSON.stringify(s[i])}`);
    }
    return { required, optional };
  };
  while (i < s.length) {
    skipSeparators();
    if (i >= s.length) break;
    const name = readName();
    if (!name) fail("expected record name");
    while (s[i] === " ") i++;
    if (s[i] === "`") i++;
    if (s[i] === "[") i++;
    const parsed = parseFields();
    if (s[i] === "]") i++;
    if (s[i] === "`") i++;
    records[alias[name] ?? name] = parsed;
    // The child template carries one parenthetical prose clause after the notes
    // record; it is not part of the bracketed field notation (asserted prose is
    // handled separately in the behavioral items below).
    while (s[i] === " ") i++;
    if (s[i] === "(") {
      while (i < s.length && s[i] !== ")") i++;
      if (s[i] === ")") i++;
    }
  }
  return records;
}

const canonFields = (list) => ({
  required: list.required.map((f) => ({ name: f.name, nested: f.nested ? canonFields(f.nested) : null })),
  optional: [...list.optional].sort(),
});

function canonProfile(profile) {
  const out = {};
  for (const key of Object.keys(profile).sort()) out[key] = canonFields(profile[key]);
  return out;
}

/** Slice one profile block out of a doc between its opening marker and terminal. */
function profileBlock(file, startMarker, terminal) {
  const text = read(file);
  const start = text.indexOf(startMarker);
  assert.ok(start !== -1, `${file}: missing profile start marker ${JSON.stringify(startMarker)}`);
  const from = start + startMarker.length;
  const end = text.indexOf(terminal, from);
  assert.ok(end !== -1, `${file}: missing profile terminal ${JSON.stringify(terminal)}`);
  return text.slice(from, end);
}

/** Every documented required field as a deletable JSON-pointer probe. */
function requiredProbes(profile) {
  const probes = [];
  for (const record of ["sources", "claims", "nonclaims", "conflicts", "notes", "missing_source_candidates"]) {
    for (const field of profile[record].required) {
      probes.push({ pointer: `/${record}/0/${field.name}`, path: [record, 0, field.name] });
      for (const nested of field.nested?.required ?? []) {
        probes.push({
          pointer: `/${record}/0/${field.name}/0/${nested.name}`,
          path: [record, 0, field.name, 0, nested.name],
        });
      }
    }
  }
  return probes;
}

function deleteAtPath(obj, parts) {
  let cursor = obj;
  for (let k = 0; k < parts.length - 1; k++) cursor = cursor[parts[k]];
  delete cursor[parts[parts.length - 1]];
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

describe("docs behavior — claims-draft/3 profile drives the verifier", () => {
  it("parses the profile from both docs and the parsed field sets agree", () => {
    const child = parseProfileBlock(profileBlock(CHILD_TEMPLATE, "Write claims-draft/3 at {claims_draft_path}:", "."));
    const intake = parseProfileBlock(profileBlock(INTAKE, "frozen S28 structural profile:", ". No magic"));
    assert.deepEqual(canonProfile(intake), canonProfile(child), "child-template and intake claims profiles must agree");
    assert.deepEqual(
      child.sources.required.map((f) => f.name),
      ["source_ref", "locator", "path", "role", "sha256", "byte_length"],
      "documented sources profile",
    );
    assert.deepEqual(child.sources.optional, ["blob_subject"], "documented sources optional");
    assert.deepEqual(
      child.conflicts.required.find((f) => f.name === "quotes").nested.required.map((f) => f.name),
      ["source_ref", "quote", "offset_bytes"],
      "documented conflict-quote profile",
    );
    assert.equal(requiredProbes(child).length, 32, "documented required-field matrix size");
  });

  it("every documented required field fails removal with shape + its own pointer", () => {
    const profile = parseProfileBlock(profileBlock(CHILD_TEMPLATE, "Write claims-draft/3 at {claims_draft_path}:", "."));
    const probes = requiredProbes(profile);
    const run = materializeRun("docs-claims-removal");
    const pristine = readText(run, CLAIMS_DRAFT);
    for (const probe of probes) {
      editJson(run, CLAIMS_DRAFT, (draft) => deleteAtPath(draft, probe.path));
      resealEnvelope(run);
      const { failed } = expectFailedCheck(
        runVerifier(["claims", "--run", run], { runRoot: run }),
        1, "shape", undefined, `delete ${probe.pointer}`,
      );
      assert.match(
        failed.detail,
        new RegExp(`^invalid field: ${escapeRe(probe.pointer)} expected `),
        `delete ${probe.pointer}: shape pointer mismatch (got ${JSON.stringify(failed.detail)})`,
      );
      writeText(run, CLAIMS_DRAFT, pristine);
      resealEnvelope(run);
    }
  });

  it("documented optional blob_subject stays optional; representative wrong types fail", () => {
    const run = materializeRun("docs-claims-types");
    const pristine = readText(run, CLAIMS_DRAFT);
    const restore = () => { writeText(run, CLAIMS_DRAFT, pristine); resealEnvelope(run); };
    const mutate = (fn, detail, label) => {
      editJson(run, CLAIMS_DRAFT, fn);
      resealEnvelope(run);
      expectFailedCheck(runVerifier(["claims", "--run", run], { runRoot: run }), 1, "shape", detail, label);
      restore();
    };

    editJson(run, CLAIMS_DRAFT, (draft) => { draft.sources[0].blob_subject = "deadbeef"; });
    resealEnvelope(run);
    expectVerdict(runVerifier(["claims", "--run", run], { runRoot: run }), 0, "blob_subject present");
    restore();
    expectVerdict(runVerifier(["claims", "--run", run], { runRoot: run }), 0, "blob_subject absent");

    mutate((draft) => { draft.sources[0].byte_length = "123"; }, "invalid field: /sources/0/byte_length expected nonnegative integer", "byte_length string");
    mutate((draft) => { draft.claims[0].also_in = "x"; }, "invalid field: /claims/0/also_in expected array", "also_in string");
    mutate((draft) => { draft.conflicts[0].quotes[0].offset_bytes = "0"; }, "invalid field: /conflicts/0/quotes/0/offset_bytes expected null or nonnegative integer", "offset_bytes string");
  });
});

describe("docs behavior — pilot policy, verifier pin, pin schema, candidate token", () => {
  it("documented pilot constants are the enforced join policy", () => {
    const pilotLine = read(INTAKE).split("\n").find((line) => line.startsWith("pilot: {"));
    assert.ok(pilotLine, "intake must carry the pilot policy line");
    const docWitness = Number(/witness_max_chars:\s*(\d+)/.exec(pilotLine)?.[1]);
    const docRetry = Number(/retry_limit:\s*(\d+)/.exec(pilotLine)?.[1]);
    const docResplit = /resplit:\s*([a-z]+)/.exec(pilotLine)?.[1];
    const docDepth = Number(/max_resplit_depth:\s*(\d+)/.exec(pilotLine)?.[1]);
    assert.equal(docWitness, 160, "documented witness bound");
    assert.equal(docRetry, 1, "documented retry limit");
    assert.equal(docResplit, "halves", "documented resplit policy");
    assert.equal(docDepth, 1, "documented resplit depth");
    assert.match(pilotLine, /operator_ref/, "documented operator ref");
    assert.match(pilotLine, /output_ceiling_bytes:\s*null/, "documented default output ceiling");
    has(CHILD_TEMPLATE, "witness_max_chars: 160", "child-template witness constant");
    has(CHILD_TEMPLATE, "one retry, halves, depth ≤ 1", "child-template recovery constants");

    const run = materializeRun("docs-pilot");
    const pristinePilot = readJson(run, RUN_MANIFEST).pilot;
    const withPilot = (mutate) => {
      editJson(run, RUN_MANIFEST, (env) => {
        env.pilot = structuredClone(pristinePilot);
        mutate(env.pilot);
      });
    };
    const probes = [
      { label: "witness_max_chars ≠ documented", mutate: (p) => { p.witness_max_chars = docWitness + 1; }, check: "join.budget", detail: "pilot witness_max_chars mismatch" },
      { label: "retry_limit ≠ documented", mutate: (p) => { p.retry_limit = docRetry + 1; }, check: "join.recovery", detail: "retry policy mismatch" },
      { label: "resplit ≠ documented", mutate: (p) => { p.resplit = "thirds"; }, check: "join.recovery", detail: "retry policy mismatch" },
      { label: "max_resplit_depth ≠ documented", mutate: (p) => { p.max_resplit_depth = docDepth + 1; }, check: "join.recovery", detail: "retry policy mismatch" },
      { label: "operator_ref missing", mutate: (p) => { delete p.operator_ref; }, check: "join.budget", detail: "pilot operator_ref missing" },
      { label: "output_ceiling_bytes wrong type", mutate: (p) => { p.output_ceiling_bytes = "1"; }, check: "join.budget", detail: "pilot output ceiling invalid" },
    ];
    for (const probe of probes) {
      withPilot(probe.mutate);
      expectFailedCheck(runVerifier(["join", "--run", run], { runRoot: run }), 1, probe.check, probe.detail, probe.label);
    }
    withPilot((p) => { p.output_ceiling_bytes = null; });
    const pass = expectVerdict(runVerifier(["join", "--run", run], { runRoot: run }), 0, "monitoring-only output ceiling");
    assert.match(findCheck(pass, "join.budget")?.detail ?? "", /monitoring only/, "null ceiling must stay monitoring-only");
  });

  it("documented verifier pin fields are enforced (path, identity, tool_version)", () => {
    const line = read(INTAKE).split("\n").find((l) => l.startsWith("verifier: {"));
    assert.ok(line, "intake must carry the verifier pin line");
    assert.equal(/path:\s*(\S+?)[,\s]/.exec(line)?.[1], "kernel/tools/verify.mjs", "documented verifier path");
    assert.match(line, /tool_version:\s*1\.0\.0/, "documented verifier tool_version");

    const run = materializeRun("docs-verifier-pin");
    const pristine = readJson(run, RUN_MANIFEST).verifier;
    const reset = () => editJson(run, RUN_MANIFEST, (env) => { env.verifier = structuredClone(pristine); });

    reset();
    editJson(run, RUN_MANIFEST, (env) => { delete env.verifier.path; });
    expectFailedCheck(runVerifier(["claims", "--run", run], { runRoot: run }), 1, "shape", "invalid field: /verifier/path expected nonempty string", "deleted verifier.path");

    reset();
    editJson(run, RUN_MANIFEST, (env) => { env.verifier.path = "kernel/tools/other.mjs"; });
    expectFailedCheck(runVerifier(["claims", "--run", run], { runRoot: run }), 1, "verifier.identity", "verifier path mismatch", "other verifier.path");

    reset();
    editJson(run, RUN_MANIFEST, (env) => { delete env.verifier.tool_version; });
    expectFailedCheck(runVerifier(["claims", "--run", run], { runRoot: run }), 1, "verifier.version", "verifier tool_version mismatch", "deleted verifier.tool_version");
  });

  it("envelope primary pin entries require a nonempty schema_version string", () => {
    const run = materializeRun("docs-pin-schema");
    editJson(run, RUN_MANIFEST, (env) => { delete env.claims_draft.schema_version; });
    expectFailedCheck(
      runVerifier(["claims", "--run", run], { runRoot: run }),
      1, "schema", "invalid field: /claims_draft/schema_version expected nonempty string",
      "claims_draft pin schema_version",
    );
  });

  it("documented primary pin lines carry exactly ref + sha256 + schema_version", () => {
    // Parse-couple the intake output-manifest pin examples so removing a field
    // from the doc (not just from the envelope) fails this suite: the tool
    // enforces a recorded ref pair and schema per primary artifact.
    for (const key of ["claims_draft", "units_manifest", "join_draft"]) {
      const line = read(INTAKE).split("\n").find((l) => l.startsWith(`${key}: {`));
      assert.ok(line, `intake must document the ${key} pin entry`);
      const names = line
        .slice(line.indexOf("{") + 1, line.indexOf("}"))
        .split(",")
        .map((part) => part.trim().split(":")[0].trim());
      assert.deepEqual(names, ["ref", "sha256", "schema_version"], `documented ${key} pin fields`);
    }
  });

  it("the enforced join candidate field is `candidate_unclaimed` end-to-end", () => {
    lacks(INTAKE, /candidate-unclaimed/, "hyphenated candidate-unclaimed");
    lacks(CHILD_TEMPLATE, /candidate-unclaimed/, "hyphenated candidate-unclaimed");
    has(INTAKE, "candidate_unclaimed[]", "enforced candidate_unclaimed token");
    has(CHILD_TEMPLATE, "candidate_unclaimed", "enforced candidate_unclaimed token");

    const run = materializeRun("docs-candidates");
    editJson(run, JOIN_DRAFT, (join) => { delete join.candidate_unclaimed; });
    resealRun(run);
    expectFailedCheck(
      runVerifier(["join", "--run", run], { runRoot: run }),
      1, "join.candidates", "invalid field: /candidate_unclaimed expected array",
      "candidate_unclaimed removal",
    );
  });
});

describe("docs behavior — envelope prep mode + fail-closed rules (fix 4 docs)", () => {
  it("intake documents `verify envelope` and every flag the tool's usage advertises", () => {
    has(INTAKE, "verify envelope", "envelope prep mode");
    has(INTAKE, "stdout only", "stdout-only rule");
    has(INTAKE, "never writes files", "no-write rule");
    has(INTAKE, "binds the envelope sha256 before the delegated", "frame-bind-before-verify rule");
    has(INTAKE, "regeneration after that freeze is not verification", "regeneration rule");
    has(INTAKE, "REFUSE envelope:", "envelope refusal summary");
    has(INTAKE, "Without `--attempts` the generator records first-attempt acceptance", "recovery-history boundary");
    has(INTAKE, "recovery semantics are validated by the delegated `verify join`", "verifier owns recovery semantics");

    const refusal = expectVerdict(runVerifier(["envelope"]), 2, "envelope usage refusal");
    const usage = findFailedCheck(refusal, "cli")?.detail ?? "";
    const flags = [...new Set(usage.match(/--[a-z-]+/g) ?? [])].sort();
    assert.ok(flags.length >= 6, `expected the tool's envelope flags, got: ${flags.join(", ")}`);
    for (const flag of flags) has(INTAKE, flag, `documented envelope flag ${flag}`);
  });

  it("intake documents the fail-closed envelope identity rules", () => {
    has(INTAKE, "`verifier.path` is exactly `kernel/tools/verify.mjs`", "verifier path rule");
    has(INTAKE, "absent or non-string fails shape", "verifier path shape rule");
    has(INTAKE, "a different path fails `verifier.identity`", "verifier path identity rule");
    has(INTAKE, "40-char lowercase hex", "oid shape rule");
    has(INTAKE, "`pilot.operator_ref` is a required nonempty string", "operator_ref rule");
    has(INTAKE, "`pilot.output_ceiling_bytes` is exactly `null`", "output ceiling rule");
    has(INTAKE, "nonnegative integer", "output ceiling int rule");
    has(INTAKE, "nonempty `schema_version` string", "pin schema_version rule");
  });

  it("CHANGELOG adds the verifier follow-up above the pinned-verifier history", () => {
    const body = read(CHANGELOG);
    const followupAt = body.indexOf("### 2026-10-04 — verifier follow-up: fail-closed envelope + prep generator");
    const pinnedAt = body.indexOf("### 2026-10-04 — pinned mechanical verifier (claims | units | join)");
    assert.ok(followupAt !== -1, "missing verifier follow-up subsection");
    assert.ok(pinnedAt !== -1 && followupAt < pinnedAt, "follow-up subsection must sit above the pinned-verifier section");
    has(CHANGELOG, "operator_ref", "pilot operator_ref");
    has(CHANGELOG, "output_ceiling_bytes", "pilot output ceiling");
    has(CHANGELOG, "verifier.path", "verifier path");
    has(CHANGELOG, "nonempty `schema_version`", "pin schema_version");
    has(CHANGELOG, "verify envelope", "envelope prep generator");
    has(CHANGELOG, "frame", "frame-bind rule");
    assert.match(body, /The coordinator gate is not a shipped tool\./, "historical 2026-10-02 sentence must remain");
  });

  it("KICKOFF §8 records envelope generation as coordinator prep before delegated verification", () => {
    has(KICKOFF, "`run-manifest.json` generation is coordinator prep via `verify envelope`", "envelope prep clause");
    has(KICKOFF, "(recording, not verification)", "recording clause");
    has(KICKOFF, "envelope sha256 is frozen in the frame before verification", "frame freeze clause");
    has(KICKOFF, "mechanical verification itself remains delegated `fast`", "delegated verification clause");
  });
});
