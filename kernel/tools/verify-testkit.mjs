// cure-light pinned-verifier testkit — shared helpers for kernel/tools/verify.test.mjs
// (and the later verify.units.test.mjs / verify.join.test.mjs suites).
//
// Node >= 22, zero dependencies, no git, no network. Every run is a fresh copy of
// the committed fixture seed under os.tmpdir(); tests never read the /home vault.
//
// CI recipe (same glob as the chunker suite):
//
//   node --test "kernel/tools/*.test.mjs"
//
// API summary:
//   materializeRun(label)      copy seed -> fresh tmp run root; when verify.mjs
//                              exists, rewrite envelope.verifier.sha256 from its
//                              actual bytes (the committed seed carries a
//                              documented placeholder; see PROVENANCE.md)
//   runVerifier(args, opts)    spawnSync(process.execPath, [verify.mjs, ...args])
//                              with a fixed minimal env (empty PATH trap dir);
//                              returns { status, signal, verdict, parseError,
//                              stdout, stderr, error }. stdout must be exactly
//                              one parseable JSON object.
//   readJson/writeJson         JSON helpers (2-space + trailing LF)
//   readBytes/writeBytes       Buffer helpers
//   sha256(buf)/artifactSha    sha256 of a buffer / of a run-relative artifact
//   editJson(run, rel, fn)     read-modify-write a JSON artifact
//   readBoxRows/writeBoxRows   parse/serialize a join box JSONL (compact, LF)
//   editBoxRow(run, boxId, unitId, fn)  mutate one box row AND its join-draft.units
//                              mirror (keeps the two copies of the row coherent)
//   resealEnvelope(run)        recompute envelope pins for capture/claims/units/
//                              payloads/join/join-box inputs/attempt outputs.
//                              Never touches verifier/chunker pins or identity.
//   resealJoinDraft(run)       recompute join_draft.boxes[].{sha256,rows,links}
//   resealP05Output(run)       recompute p05-evidence budget.output_bytes/output_links
//   resealRun(run)             resealJoinDraft + resealP05Output + resealEnvelope
//   snapshotTree(run)          sorted [{rel,bytes,sha256}] for no-write assertions
//
// Resealing is deliberately opt-in and only repairs OUTER pins/derived summaries.
// A test that targets a pin or an envelope field must mutate it after (or instead
// of) resealing; a test that wants a stale-pin failure simply skips the helper.
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync,
  rmSync, writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const TOOLS_DIR = path.dirname(fileURLToPath(import.meta.url));
export const VERIFY_PATH = path.join(TOOLS_DIR, "verify.mjs");
export const FIXTURES_DIR = path.join(TOOLS_DIR, "verify-fixtures");
export const SEED_DIR = path.join(FIXTURES_DIR, "seed");
export const RAW_WITNESSES_PATH = path.join(FIXTURES_DIR, "raw-s28-witnesses.json");

export const RUN_MANIFEST = "run-manifest.json";
export const CLAIMS_DRAFT = "claims/claims-draft.v3.json";
export const CAPTURE_MANIFEST = "claims/sources/capture-manifest.json";
export const UNITS_MANIFEST = "units/units2/manifest.json";
export const JOIN_DRAFT = "join/join-draft.v1.json";
export const BOX_0000 = "join/box-0000.jsonl";
export const BOX_0000_ASSIGNMENT = "join/box-0000.assignment.json";
export const BOX_0000_INSTRUCTIONS = "join/box-0000.instructions.md";
export const CLAIMS_LIST = "join/claims-list.json";
export const P05_CHECK = "join/p05-check.json";
export const P05_EVIDENCE = "join/p05-evidence.json";

const tempDirs = new Set();
const traps = new Map();
let defaultTrap = null;

/** Allocate and register a unique directory under os.tmpdir(). */
export function tempDir(prefix) {
  const dir = mkdtempSync(path.join(os.tmpdir(), `cure-light-${prefix}-`));
  tempDirs.add(dir);
  return dir;
}

/** Remove every directory allocated by this module (wire to `after(cleanupTempDirs)`). */
export function cleanupTempDirs() {
  for (const dir of tempDirs) {
    try { rmSync(dir, { recursive: true, force: true, maxRetries: 3 }); } catch { /* best effort */ }
  }
  tempDirs.clear();
  traps.clear();
  defaultTrap = null;
}

function ensureTrap() {
  if (!defaultTrap) {
    defaultTrap = tempDir("empty-bin");
    mkdirSync(defaultTrap, { recursive: true });
  }
  return defaultTrap;
}

/**
 * Copy the committed seed to a fresh run root under os.tmpdir().
 * Returns the absolute run-root path. When kernel/tools/verify.mjs exists, the
 * envelope verifier.sha256 placeholder is replaced with the real file hash so
 * fixtures exercise the live tool; missing tool leaves the placeholder and the
 * suite is expected to be red.
 */
export function materializeRun(label = "run") {
  const base = tempDir(`verify-${label}`);
  const runRoot = path.join(base, "run");
  cpSync(SEED_DIR, runRoot, { recursive: true });
  const trap = path.join(base, "empty-bin");
  mkdirSync(trap, { recursive: true });
  traps.set(runRoot, trap);
  if (existsSync(VERIFY_PATH)) {
    editJson(runRoot, RUN_MANIFEST, (env) => {
      env.verifier.sha256 = sha256(readFileSync(VERIFY_PATH));
    });
  }
  return runRoot;
}

export function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

export function artifactSha(runRoot, rel) {
  return sha256(readFileSync(path.join(runRoot, rel)));
}

export function readBytes(runRoot, rel) {
  return readFileSync(path.join(runRoot, rel));
}

export function writeBytes(runRoot, rel, buf) {
  const abs = path.join(runRoot, rel);
  mkdirSync(path.dirname(abs), { recursive: true });
  writeFileSync(abs, buf);
}

export function readText(runRoot, rel) {
  return readFileSync(path.join(runRoot, rel), "utf8");
}

export function writeText(runRoot, rel, text) {
  writeBytes(runRoot, rel, Buffer.from(text, "utf8"));
}

export function readJson(runRoot, rel) {
  return JSON.parse(readFileSync(path.join(runRoot, rel), "utf8"));
}

export function writeJson(runRoot, rel, obj) {
  writeText(runRoot, rel, JSON.stringify(obj, null, 2) + "\n");
}

/** Read-modify-write one JSON artifact; `fn` receives the parsed object. */
export function editJson(runRoot, rel, fn) {
  const obj = readJson(runRoot, rel);
  fn(obj);
  writeJson(runRoot, rel, obj);
  return obj;
}

/** Parse a join box JSONL into row objects. */
export function readBoxRows(runRoot, rel = BOX_0000) {
  return readText(runRoot, rel).split("\n").filter((line) => line.length > 0).map((line) => JSON.parse(line));
}

/** Serialize rows as the verifier's compact JSONL (one row per line, trailing LF). */
export function writeBoxRows(runRoot, rel, rows) {
  writeText(runRoot, rel, rows.map((row) => JSON.stringify(row)).join("\n") + "\n");
}

/**
 * Mutate exactly one box row (matched by unit_id) and keep the join-draft.units
 * mirror coherent. `fn(row)` edits the parsed row in place; `fn` must not touch
 * `unit_id`. Then reseal with resealRun() (or targeted helpers) to refresh pins.
 */
export function editBoxRow(runRoot, boxId, unitId, fn, boxRel = BOX_0000) {
  const rows = readBoxRows(runRoot, boxRel);
  const index = rows.findIndex((r) => r.unit_id === unitId);
  if (index < 0) throw new Error(`unknown box row: ${boxId}/${unitId}`);
  fn(rows[index]);
  writeBoxRows(runRoot, boxRel, rows);
  const join = readJson(runRoot, JOIN_DRAFT);
  const mirrorIndex = join.units.findIndex((r) => r.unit_id === unitId);
  if (mirrorIndex >= 0) join.units[mirrorIndex] = structuredClone(rows[index]);
  writeJson(runRoot, JOIN_DRAFT, join);
  return rows;
}

/** Recompute join_draft.boxes[].{sha256,rows,links} from the box files. */
export function resealJoinDraft(runRoot) {
  const join = readJson(runRoot, JOIN_DRAFT);
  for (const box of join.boxes) {
    const buf = readBytes(runRoot, box.path);
    box.sha256 = sha256(buf);
    const lines = buf.toString("utf8").split("\n").filter((line) => line.length > 0);
    box.rows = lines.length;
    let links = 0;
    let linksValid = true;
    for (const line of lines) {
      try {
        const parsed = JSON.parse(line);
        if (!Array.isArray(parsed.links)) { linksValid = false; break; }
        links += parsed.links.length;
      } catch {
        linksValid = false;
        break;
      }
    }
    if (linksValid) box.links = links;
  }
  writeJson(runRoot, JOIN_DRAFT, join);
  return join;
}

/** Recompute p05-evidence output metrics from the recorded box outputs. */
export function resealP05Output(runRoot) {
  const envelope = readJson(runRoot, RUN_MANIFEST);
  const p05 = readJson(runRoot, P05_EVIDENCE);
  let bytes = 0;
  let links = 0;
  let allParsed = true;
  for (const attempt of envelope.join_attempts) {
    const buf = readBytes(runRoot, attempt.output.ref);
    bytes += buf.length;
    for (const line of buf.toString("utf8").split("\n").filter((l) => l.length > 0)) {
      try { links += JSON.parse(line).links.length; } catch { allParsed = false; }
    }
  }
  p05.budget.output_bytes = bytes;
  if (allParsed) p05.budget.output_links = links;
  writeJson(runRoot, P05_EVIDENCE, p05);
  return p05;
}

function payloadAbs(runRoot, unitsRef, ref) {
  return path.join(runRoot, path.dirname(path.dirname(unitsRef)), ref);
}

/** Recompute every outer envelope pin from the current artifact bytes. */
export function resealEnvelope(runRoot) {
  const envelope = readJson(runRoot, RUN_MANIFEST);
  envelope.capture_manifest.sha256 = artifactSha(runRoot, envelope.capture_manifest.ref);
  envelope.claims_draft.sha256 = artifactSha(runRoot, envelope.claims_draft.ref);
  envelope.units_manifest.sha256 = artifactSha(runRoot, envelope.units_manifest.ref);
  const manifest = readJson(runRoot, envelope.units_manifest.ref);
  envelope.unit_payloads = manifest.units.map((u) => ({
    unit_id: u.unit_id,
    ref: u.file,
    sha256: sha256(readFileSync(payloadAbs(runRoot, envelope.units_manifest.ref, u.file))),
  }));
  envelope.join_draft.sha256 = artifactSha(runRoot, envelope.join_draft.ref);
  for (const box of envelope.join_boxes) {
    for (const key of ["assignment", "instructions", "claims_list", "p05_check", "p05_evidence"]) {
      box[key].sha256 = artifactSha(runRoot, box[key].ref);
    }
  }
  for (const attempt of envelope.join_attempts) {
    attempt.output.sha256 = artifactSha(runRoot, attempt.output.ref);
  }
  writeJson(runRoot, RUN_MANIFEST, envelope);
  return envelope;
}

/** resealJoinDraft -> resealP05Output -> resealEnvelope (order matters). */
export function resealRun(runRoot) {
  resealJoinDraft(runRoot);
  resealP05Output(runRoot);
  return resealEnvelope(runRoot);
}

/** Sorted content snapshot of the run root for {"no writes happened"} assertions. */
export function snapshotTree(runRoot) {
  const out = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(abs);
      else {
        const buf = readFileSync(abs);
        out.push({ rel: path.relative(runRoot, abs).split(path.sep).join("/"), bytes: buf.length, sha256: sha256(buf) });
      }
    }
  };
  walk(runRoot);
  return out;
}

function parseVerdict(stdout) {
  if (stdout.trim() === "") return { verdict: null, parseError: "stdout is empty (no verdict)" };
  let parsed;
  try {
    parsed = JSON.parse(stdout);
  } catch (err) {
    return { verdict: null, parseError: `stdout is not exactly one JSON value: ${err.message}` };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { verdict: null, parseError: "stdout JSON is not a verdict object" };
  }
  return { verdict: parsed, parseError: null };
}

/**
 * Run the pinned verifier. `args` excludes the executable path. The subprocess
 * gets a minimal fixed environment whose PATH points at an empty trap dir, so
 * the verifier cannot silently depend on git/network/PATH tools. Node itself is
 * launched through the absolute process.execPath.
 */
export function runVerifier(args, { runRoot, cwd, env = {}, timeout = 30_000 } = {}) {
  const trap = (runRoot && traps.get(runRoot)) ?? ensureTrap();
  const childEnv = {
    PATH: trap,
    HOME: trap,
    TMPDIR: os.tmpdir(),
    TMP: os.tmpdir(),
    TEMP: os.tmpdir(),
    LANG: "C",
    LC_ALL: "C",
    NO_COLOR: "1",
    ...env,
  };
  const res = spawnSync(process.execPath, [VERIFY_PATH, ...args], {
    encoding: "utf8",
    cwd: cwd ?? runRoot ?? os.tmpdir(),
    env: childEnv,
    timeout,
    maxBuffer: 1 << 26,
  });
  const stdout = res.stdout ?? "";
  const { verdict, parseError } = parseVerdict(stdout);
  return {
    status: res.status,
    signal: res.signal,
    error: res.error,
    stdout,
    stderr: res.stderr ?? "",
    verdict,
    parseError,
    command: `${process.execPath} ${VERIFY_PATH} ${args.join(" ")}`,
  };
}

/** First check matching `name` (pass or fail), or undefined. */
export function findCheck(verdict, name) {
  return verdict?.checks?.find((c) => c.name === name);
}

/** First FAILED check matching `name`, or undefined. */
export function findFailedCheck(verdict, name) {
  return verdict?.checks?.find((c) => c.name === name && c.ok === false);
}

// ---------------------------------------------------------------------------
// join fixture synthesis (plan §4 items 12–28)
//
// The committed seed stays untouched: every helper below derives a variant in
// the per-test tmpdir. Resealing is deliberate and limited to outer pins plus
// the recorded derived summaries (box rows/links, p05 output bytes, the
// join-draft.units_manifest binding, envelope pins).
// ---------------------------------------------------------------------------

/** Absolute path of one unit payload from the current units manifest. */
export function unitPayloadAbs(runRoot, unitId) {
  const manifest = readJson(runRoot, UNITS_MANIFEST);
  const unit = manifest.units.find((u) => u.unit_id === unitId);
  if (!unit) throw new Error(`unknown unit: ${unitId}`);
  return payloadAbs(runRoot, UNITS_MANIFEST, unit.file);
}

/**
 * Refresh the join-draft.units_manifest binding after a units-manifest change,
 * then reseal the envelope (payload pins included). Callers that mutated the
 * manifest must use this instead of a bare resealEnvelope().
 */
export function resealUnitsBinding(runRoot) {
  const manifest = readJson(runRoot, UNITS_MANIFEST);
  const manifestSha = artifactSha(runRoot, UNITS_MANIFEST);
  editJson(runRoot, JOIN_DRAFT, (join) => {
    join.units_manifest.sha256 = manifestSha;
    join.units_manifest.unit_count = manifest.units.length;
  });
  editJson(runRoot, BOX_0000_ASSIGNMENT, (assignment) => {
    const byteLen = new Map(manifest.units.map((u) => [u.unit_id, u.byte_len]));
    assignment.manifest_sha256 = manifestSha;
    assignment.total_unit_bytes = assignment.units.reduce((n, id) => n + (byteLen.get(id) ?? 0), 0);
  });
  const unitBytes = manifest.units.reduce((n, u) => n + u.byte_len, 0);
  editJson(runRoot, P05_EVIDENCE, (p05) => {
    p05.budget.unit_bytes = unitBytes;
    p05.budget.box_input_bytes = unitBytes + p05.budget.claims_list_bytes + p05.budget.instructions_bytes;
    p05.budget.headroom_bytes = p05.budget.input_ceiling_bytes - p05.budget.box_input_bytes;
  });
  return resealEnvelope(runRoot);
}

/**
 * Append one payload line (introduced by "\n") to a unit, update the manifest
 * byte_len/counts.total_bytes, refresh the join units_manifest binding and
 * reseal. Returns the new payload bytes. Used for long/astral witness cases;
 * the caller must pass a diff-marked line (e.g. "+xxx") so U7 stays happy.
 */
export function appendPayloadLine(runRoot, unitId, line) {
  const manifest = readJson(runRoot, UNITS_MANIFEST);
  const unit = manifest.units.find((u) => u.unit_id === unitId);
  if (!unit) throw new Error(`unknown unit: ${unitId}`);
  const abs = payloadAbs(runRoot, UNITS_MANIFEST, unit.file);
  const before = readFileSync(abs);
  const after = Buffer.concat([before, Buffer.from(`\n${line}`, "utf8")]);
  writeFileSync(abs, after);
  editJson(runRoot, UNITS_MANIFEST, (m) => {
    const u = m.units.find((x) => x.unit_id === unitId);
    m.counts.total_bytes += after.length - u.byte_len;
    u.byte_len = after.length;
  });
  resealUnitsBinding(runRoot);
  return after;
}

/**
 * Convert one block unit into a genuine no-hunk metadata `file` unit (doc
 * comment: same shape as the units-suite metadata synthesis). The payload is a
 * metadata-only diff for the unit's own path, so U6/U7 keep passing and a
 * witness may legitimately start at a `diff --git ` line. Returns the first
 * payload line (a valid metadata witness for the unit).
 */
export function makeMetadataFileUnit(runRoot, unitId = "u0000") {
  const manifest = readJson(runRoot, UNITS_MANIFEST);
  const unit = manifest.units.find((u) => u.unit_id === unitId);
  if (!unit) throw new Error(`unknown unit: ${unitId}`);
  const payload = [
    `diff --git a/${unit.path} b/${unit.path}`,
    "new file mode 100644",
    "index 0000000..1111111",
    `Binary files /dev/null and b/${unit.path} differ`,
  ].join("\n");
  const payloadBuf = Buffer.from(payload, "utf8");
  writeFileSync(payloadAbs(runRoot, UNITS_MANIFEST, unit.file), payloadBuf);
  editJson(runRoot, UNITS_MANIFEST, (m) => {
    const u = m.units.find((x) => x.unit_id === unitId);
    m.counts.total_bytes += payloadBuf.length - u.byte_len;
    u.byte_len = payloadBuf.length;
    u.boundary_kind = "file";
    u.ranges = [];
    u.hunk_count = 0;
    u.blocks = 1;
  });
  resealUnitsBinding(runRoot);
  return `diff --git a/${unit.path} b/${unit.path}`;
}

/** Make one row link-free (optionally unresolved) and reseal the whole run. */
export function setRowUnlinked(runRoot, unitId, unresolved = null, boxRel = BOX_0000) {
  editBoxRow(runRoot, "box-0000", unitId, (row) => {
    row.links = [];
    row.unresolved = unresolved;
  }, boxRel);
  resealRun(runRoot);
  return readBoxRows(runRoot, boxRel).find((r) => r.unit_id === unitId);
}

/** Serialize one attempt output JSONL and return its sha256 pin. */
export function writeAttemptOutput(runRoot, ref, rows) {
  writeBoxRows(runRoot, ref, rows);
  return artifactSha(runRoot, ref);
}

/**
 * Replace envelope.join_attempts with structured records (plan §2 shape).
 * `attempts` entries: {attemptId, boxId, parentBoxId?, attempt, units,
 * outputRef, status}; every outputRef must already exist on disk.
 */
export function setJoinAttempts(runRoot, attempts) {
  const env = readJson(runRoot, RUN_MANIFEST);
  env.join_attempts = attempts.map((a) => ({
    attempt_id: a.attemptId,
    box_id: a.boxId,
    parent_box_id: a.parentBoxId ?? null,
    attempt: a.attempt,
    units: a.units,
    output: { ref: a.outputRef, sha256: artifactSha(runRoot, a.outputRef) },
    status: a.status,
  }));
  writeJson(runRoot, RUN_MANIFEST, env);
  return env.join_attempts;
}

/**
 * Split the seed's single box into two current boxes at `splitIndex` rows.
 * Writes join/<boxId>.jsonl, join/<boxId>.assignment.json,
 * join/<boxId>.p05-check.json and join/<boxId>.p05-evidence.json for both
 * boxes (the seed instructions/claims-list files are reused), rewrites
 * join-draft boxes, and records one accepted attempt-1 per box. The merge
 * (join.units) is untouched. resealEnvelope() is applied.
 * Returns { boxIds, unitIds: [leftIds, rightIds] }.
 */
export function splitIntoTwoBoxes(runRoot, splitIndex = 23, boxIds = ["box-0000", "box-0001"]) {
  const rows = readBoxRows(runRoot, BOX_0000);
  if (splitIndex <= 0 || splitIndex >= rows.length) throw new Error("splitIndex must produce two nonempty halves");
  const halves = [rows.slice(0, splitIndex), rows.slice(splitIndex)];
  const manifest = readJson(runRoot, UNITS_MANIFEST);
  const byteLen = new Map(manifest.units.map((u) => [u.unit_id, u.byte_len]));
  const baseAssignment = readJson(runRoot, BOX_0000_ASSIGNMENT);
  const claimIds = readJson(runRoot, CLAIMS_LIST).map((c) => c.id);
  const claimsListBytes = readBytes(runRoot, CLAIMS_LIST).length;
  const instructionsBytes = readBytes(runRoot, BOX_0000_INSTRUCTIONS).length;
  const boxEntries = [];
  const unitIds = [];
  for (let h = 0; h < 2; h++) {
    const boxId = boxIds[h];
    const outputRel = `join/${boxId}.jsonl`;
    const assignmentRel = `join/${boxId}.assignment.json`;
    writeBoxRows(runRoot, outputRel, halves[h]);
    const ids = halves[h].map((r) => r.unit_id);
    unitIds.push(ids);
    const unitBytes = ids.reduce((n, id) => n + byteLen.get(id), 0);
    const links = halves[h].reduce((n, r) => n + r.links.length, 0);
    writeJson(runRoot, assignmentRel, {
      ...baseAssignment,
      box_id: boxId,
      output_path: outputRel,
      units: ids,
      unit_count: ids.length,
      total_unit_bytes: unitBytes,
    });
    const zeroUnits = halves[h].filter((r) => r.links.length === 0).map((r) => r.unit_id);
    const unresolved = halves[h].filter((r) => r.unresolved !== null).map((r) => r.unit_id);
    const claimCounts = new Map(claimIds.map((id) => [id, 0]));
    const pairSeen = new Set();
    let duplicatePairs = 0;
    for (const row of halves[h]) {
      for (const link of row.links) {
        claimCounts.set(link.claim_id, (claimCounts.get(link.claim_id) ?? 0) + 1);
        const key = `${row.unit_id}/${link.claim_id}`;
        if (pairSeen.has(key)) duplicatePairs += 1;
        else pairSeen.add(key);
      }
    }
    const zeroClaims = claimIds.filter((id) => (claimCounts.get(id) ?? 0) === 0);
    const p05CheckRel = `join/${boxId}.p05-check.json`;
    const p05EvidenceRel = `join/${boxId}.p05-evidence.json`;
    writeJson(runRoot, p05CheckRel, {
      file_rows: ids.length,
      expected_rows: ids.length,
      total_links: links,
      zero_units: zeroUnits,
      zero_claims: zeroClaims,
      unresolved,
      error_count: 0,
      errors: [],
      claim_link_counts: Object.fromEntries(claimCounts),
    });
    const boxInputBytes = unitBytes + claimsListBytes + instructionsBytes;
    writeJson(runRoot, p05EvidenceRel, {
      check: "p05-coordinator-gate",
      box: boxId,
      expected_rows: ids.length,
      received_rows: ids.length,
      total_links: links,
      zero_units: zeroUnits,
      zero_claims: zeroClaims,
      unresolved,
      error_count: 0,
      errors: [],
      witness_containment: `synthesized two-box fixture (${links} links)`, 
      duplicate_pairs: duplicatePairs,
      retry_history: "synthesized two-box fixture (both boxes accepted first attempt)",
      budget: {
        input_ceiling_bytes: baseAssignment.input_ceiling_bytes,
        unit_bytes: unitBytes,
        claims_list_bytes: claimsListBytes,
        instructions_bytes: instructionsBytes,
        box_input_bytes: boxInputBytes,
        headroom_bytes: baseAssignment.input_ceiling_bytes - boxInputBytes,
        output_bytes: readBytes(runRoot, outputRel).length,
        output_links: links,
      },
    });
    boxEntries.push({
      box_id: boxId,
      path: outputRel,
      sha256: artifactSha(runRoot, outputRel),
      rows: ids.length,
      links,
    });
  }
  const boxRefs = boxEntries.map((box) => ({
    box_id: box.box_id,
    assignment: { ref: `join/${box.box_id}.assignment.json` },
    instructions: { ref: BOX_0000_INSTRUCTIONS },
    claims_list: { ref: CLAIMS_LIST },
    p05_check: { ref: `join/${box.box_id}.p05-check.json` },
    p05_evidence: { ref: `join/${box.box_id}.p05-evidence.json` },
  }));
  editJson(runRoot, JOIN_DRAFT, (join) => {
    join.boxes = boxEntries;
  });
  editJson(runRoot, RUN_MANIFEST, (env) => {
    env.join_boxes = boxRefs;
    env.join_attempts = boxEntries.map((box, h) => ({
      attempt_id: `${box.box_id}-a1`,
      box_id: box.box_id,
      parent_box_id: null,
      attempt: 1,
      units: unitIds[h],
      output: { ref: box.path },
      status: "accepted",
    }));
  });
  resealEnvelope(runRoot);
  return { boxIds, unitIds };
}

/**
 * Empty-inventory run (plan §4 item 28): units manifest with zero units/files/
 * bytes, capture changed_files [], join-draft boxes/units/candidate_unclaimed
 * all [], envelope join_boxes [] and join_attempts []. All single-box seed
 * artifacts (payloads, box, assignment, instructions, claims-list, p05) are
 * removed so the representation is unambiguous. Claims stay nonempty with all
 * zero-link claims reported globally by the (later) J11/J12 work.
 */
export function materializeEmptyRun(label = "empty") {
  const runRoot = materializeRun(label);
  for (const rel of [BOX_0000, BOX_0000_ASSIGNMENT, BOX_0000_INSTRUCTIONS, CLAIMS_LIST, P05_CHECK, P05_EVIDENCE]) {
    rmSync(path.join(runRoot, rel), { force: true });
  }
  const unitsDir = path.join(runRoot, "units/units2");
  for (const name of readdirSync(unitsDir)) {
    if (name !== "manifest.json") rmSync(path.join(unitsDir, name), { force: true });
  }
  editJson(runRoot, CAPTURE_MANIFEST, (capture) => {
    capture.changed_files = [];
    capture.changed_files_count = 0;
  });
  editJson(runRoot, UNITS_MANIFEST, (manifest) => {
    manifest.units = [];
    manifest.counts = { units: 0, files: 0, line_split_units: 0, total_bytes: 0 };
  });
  const seedJoin = readJson(runRoot, JOIN_DRAFT);
  writeJson(runRoot, JOIN_DRAFT, {
    schema_version: "join-draft/1",
    run: seedJoin.run,
    review_state: seedJoin.review_state,
    subject_oid: seedJoin.subject_oid,
    base_oid: seedJoin.base_oid,
    units_manifest: {
      ref: UNITS_MANIFEST,
      sha256: artifactSha(runRoot, UNITS_MANIFEST),
      schema_version: "code-units-sim/2",
      unit_count: 0,
    },
    boxes: [],
    units: [],
    candidate_unclaimed: [],
  });
  editJson(runRoot, RUN_MANIFEST, (env) => {
    env.join_boxes = [];
    env.join_attempts = [];
  });
  resealEnvelope(runRoot);
  return runRoot;
}

/**
 * Derive a /3 run with one first-class opaque descriptor and raw occurrences.
 * No seed or existing helper is modified. Defaults to a certified byte-identical
 * removed/added pair. Overrides support unpaired/ambiguous and malformed-case
 * fixtures; mutateManifest runs after the coherent defaults and before resealing.
 *
 * options: { bodies?: [Buffer|string, ...], sides?, states?, pairId?, path?,
 *   coverage?, skips?, descriptor?, mutateManifest? }. Each body is the exact
 * line body, excluding diff marker and terminator (CR, if present, is retained).
 * Returns {runRoot, unitId, occurrenceIds, rawRefs, bodies, descriptorRef}.
 */
export function materializeOpaqueRun(label = "opaque", options = {}) {
  const runRoot = materializeRun(label);
  const unitId = "u0046";
  const descriptorRef = `units2/${unitId}.txt`;
  const pathName = options.path ?? ".gitignore"; // already in the seed changed_files sweep
  const bodies = (options.bodies ?? [Buffer.alloc(7000, 0x51), Buffer.alloc(7000, 0x51)])
    .map((body) => Buffer.from(body));
  const sides = options.sides ?? ["removed", "added"];
  const pairId = options.pairId === undefined ? "pair-0000" : options.pairId;
  if (bodies.length !== sides.length) throw new Error("opaque bodies/sides length mismatch");
  const occurrenceIds = bodies.map((_, i) => `occ-${String(i).padStart(4, "0")}`);
  const rawRefs = occurrenceIds.map((id) => `units2/raw/${id}.bin`);
  const occurrences = bodies.map((body, i) => ({
    occurrence_id: occurrenceIds[i], path: pathName, side: sides[i],
    byte_length: body.length, sha256: sha256(body), ref: rawRefs[i],
    pair_id: pairId, state: options.states?.[i] ?? (pairId === null ? "unpaired" : "paired"),
  }));
  const descriptor = options.descriptor ?? {
    schema: "opaque-descriptor/1", unit_id: unitId,
    occurrences: occurrences.map(({ occurrence_id, side, byte_length, sha256: hash }) =>
      ({ occurrence_id, side, byte_length, sha256: hash })),
    pairing: pairId === null ? null : { pair_id: pairId, occurrence_ids: occurrenceIds },
  };
  const descriptorBytes = Buffer.from(JSON.stringify(descriptor), "utf8");
  writeBytes(runRoot, `units/${descriptorRef}`, descriptorBytes);
  for (let i = 0; i < bodies.length; i++) writeBytes(runRoot, `units/${rawRefs[i]}`, bodies[i]);
  editJson(runRoot, UNITS_MANIFEST, (manifest) => {
    manifest.schema_version = "code-units-sim/3";
    manifest.units.push({
      unit_id: unitId, file: descriptorRef, path: pathName, ranges: [],
      hunk_count: 0, byte_len: descriptorBytes.length, blocks: 1,
      boundary_kind: "opaque",
    });
    manifest.opaque_occurrences = occurrences;
    manifest.coverage = options.coverage ?? { status: "complete", machine_occurrences: occurrences.length, skips: [] };
    manifest.skips = options.skips ?? [];
    manifest.counts.units = manifest.units.length;
    manifest.counts.total_bytes += descriptorBytes.length;
    manifest.counts.opaque_occurrences = occurrences.length;
    manifest.counts.opaque_bytes = bodies.reduce((total, body) => total + body.length, 0);
    options.mutateManifest?.(manifest);
  });
  editJson(runRoot, RUN_MANIFEST, (env) => {
    env.units_manifest.schema_version = "code-units-sim/3";
  });
  resealUnitsBinding(runRoot);
  editJson(runRoot, JOIN_DRAFT, (join) => {
    join.units_manifest.schema_version = "code-units-sim/3";
  });
  resealEnvelope(runRoot);
  return { runRoot, unitId, occurrenceIds, rawRefs, bodies, descriptorRef };
}

/** Add the mandatory machine-only row for one opaque manifest unit. */
export function addOpaqueMachineRow(runRoot, unitId, unresolved = null) {
  editJson(runRoot, JOIN_DRAFT, (join) => {
    join.machine ??= [];
    join.machine.push({ unit_id: unitId, links: [], unresolved });
  });
  resealEnvelope(runRoot);
  return readJson(runRoot, JOIN_DRAFT).machine;
}

/**
 * Write and pin the operator approval artifact for the run's recorded skips.
 * Overrides may replace identity fields or approved entries for negative cases.
 */
export function writeOperatorApproval(runRoot, { ref = "approvals/operator-approval.json", approved, ...overrides } = {}) {
  const env = readJson(runRoot, RUN_MANIFEST);
  const manifest = readJson(runRoot, UNITS_MANIFEST);
  const defaultApproved = (manifest.skips ?? []).map((skip) => ({
    skip_id: skip.skip_id,
    occurrence_ids: structuredClone(skip.occurrence_ids),
    policy_class: "big-blob",
    rationale: "fixture operator approval for recorded partial coverage",
    basis: "partial-review",
  }));
  const approval = {
    schema_version: "operator-approval/1",
    run: env.run,
    review_state: env.review_state,
    base_oid: env.base_oid,
    subject_oid: env.subject_oid,
    operator_ref: env.pilot.operator_ref,
    approved: approved ?? defaultApproved,
    ...overrides,
  };
  writeJson(runRoot, ref, approval);
  editJson(runRoot, RUN_MANIFEST, (updated) => {
    updated.pilot.approval = { ref, sha256: artifactSha(runRoot, ref) };
  });
  return { ref, approval };
}
