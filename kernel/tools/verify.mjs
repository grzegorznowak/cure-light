#!/usr/bin/env node
// kernel/tools/verify.mjs — cure-light pinned mechanical verifier.
//
// PURPOSE
//   Read-only, zero-dependency mechanical validator for recorded cure-light run
//   artifacts. It validates the recorded evidence envelope and the claims /
//   units / join artifacts described by the frozen plan contract; it never
//   executes the subject, never calls git/network tools, never writes run
//   artifacts, and never decides semantic readiness.
//
// USAGE
//   verify <claims|units|join> --run <run-root>
//   (actual invocation: node <pinned-engine>/kernel/tools/verify.mjs <claims|units|join> --run <run-root>)
//
// EXIT CODES
//   0  every check passed
//   1  validation failure (ok=false, summary "FAIL ...")
//   2  usage refusal or unknown/unsupported schema_version (summary "REFUSE ...")
//
// SUPPORTED SCHEMAS
//   run-verification/1  envelope at <run-root>/run-manifest.json
//   claims-draft/3      claims/claims-draft*.json
//   code-units-sim/2    units/units2/manifest.json | units2/manifest.json
//   join-draft/1        join/join-draft*.json
//   Unknown schemas anywhere in the required graph refuse with exit 2.
//   Stdout is exactly one JSON verdict:
//     {ok,tool_version,schema,checks:[{name,ok,detail}],summary}
//
// TESTS
//   node --test "kernel/tools/*.test.mjs"

import { createHash } from "node:crypto";
import { readFileSync, readdirSync, realpathSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const TOOL_VERSION = "1.0.0";
const VERIFY_PATH = fileURLToPath(import.meta.url);
const USAGE = "usage: verify <claims|units|join> --run <run-root>";
const ENVELOPE_REF = "run-manifest.json";
const COMMANDS = new Set(["claims", "units", "join"]);

// Registry is keyed by schema_version; `family` is the command that owns it.
// The envelope is a distinct family so a claims/units/join schema in the
// envelope slot (or vice versa) is a supported-but-wrong-kind refusal.
const REGISTRY = new Map([
  ["run-verification/1", { family: "envelope" }],
  ["claims-draft/3", { family: "claims" }],
  ["code-units-sim/2", { family: "units" }],
  ["join-draft/1", { family: "join" }],
]);

const PRIMARY_PIN_FIELD = { claims: "claims_draft", units: "units_manifest", join: "join_draft" };
const PRIMARY_KIND = { claims: "claims-draft", units: "units-manifest", join: "join-draft" };

// Frozen code-units-sim/2 recipe (plan §3 U2): both the manifest recipe and the
// envelope's recorded chunker recipe must equal these constants exactly.
const UNITS_RECIPE = Object.freeze({
  chunker: "chunker.mjs",
  target_bytes: 4096,
  ceiling_bytes: 6144,
  context: 3,
  block_preference: true,
});
const BOUNDARY_KINDS = new Set(["file", "block", "line-split"]);
const PAYLOAD_BASENAME = /^u\d{4}\.txt$/;

// Preamble/metadata lines the chunker can carry in a payload (no prefix-order
// ambiguity with +/-, which are checked after). Mirrors the frozen witness
// metadata policy so the two never drift.
const METADATA_PREFIXES = [
  "diff --git ", "index ", "--- ", "+++ ", "new file mode ", "deleted file mode ",
  "old mode ", "new mode ", "rename from ", "rename to ", "similarity index ",
  "copy from ", "copy to ", "Binary files ",
];

// ---------------------------------------------------------------------------
// small helpers
// ---------------------------------------------------------------------------

const q = (value) => JSON.stringify(String(value));
const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");
const isPlainObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isNonEmptyString = (v) => typeof v === "string" && v.length > 0;
const isNonNegInt = (v) => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const toPosix = (p) => (path.sep === "/" ? p : p.split(path.sep).join("/"));
const firstLine = (text) => String(text).split("\n", 1)[0];
const sameArray = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => v === b[i]);

/** Canonical JSON projection: object key order ignored, array order preserved. */
function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (isPlainObject(value)) {
    const out = {};
    for (const key of Object.keys(value).sort()) out[key] = canonicalJson(value[key]);
    return out;
  }
  return value;
}

const utf8Decoder = new TextDecoder("utf-8", { fatal: true });
function decodeUtf8(buf) {
  try {
    return utf8Decoder.decode(buf);
  } catch {
    return null;
  }
}

/** UTF-8 BOM prefix: rejected deterministically, never silently stripped. */
function hasUtf8Bom(buf) {
  return buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf;
}

// Payload lines. The historical corpus contains payloads that end with one LF
// (byte_len accounts for it), so one final LF is treated as a terminator, never
// as an empty diff line.
function splitPayloadLines(text) {
  const lines = text.split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
  return lines;
}

/** Classify one payload line: "metadata" | "hunk" | "content" | null (invalid). */
function classifyDiffLine(line) {
  for (const prefix of METADATA_PREFIXES) if (line.startsWith(prefix)) return "metadata";
  if (line.startsWith("@@ ")) return "hunk";
  if (line.startsWith("\\ ")) return "content"; // "\\ No newline at end of file"
  const head = line[0];
  if (head === "+" || head === "-" || head === " ") return "content";
  return null;
}

/**
 * Exact path from a `diff --git a/X b/X` header, mirroring the chunker's
 * longest-equal-span recovery. Returns null when no exact unquoted split exists
 * (C-quoted paths are not an exact representation).
 */
function gitHeaderPath(line) {
  const prefix = "diff --git a/";
  if (!line.startsWith(prefix)) return null;
  const rest = line.slice(prefix.length);
  if (rest.startsWith('"')) return null;
  let best = null;
  for (let p = rest.indexOf(" b/"); p !== -1; p = rest.indexOf(" b/", p + 1)) {
    const left = rest.slice(0, p);
    const right = rest.slice(p + 3);
    if (left.length > 0 && left === right && (best === null || left.length > best.length)) best = left;
  }
  return best;
}

/** Exact path from `--- a/X` (sign "a") / `+++ b/X` (sign "b"); null otherwise. */
function signedDiffPath(line, sign) {
  const rest = line.slice(4);
  if (rest === "/dev/null" || !rest.startsWith(`${sign}/`)) return null;
  const pathPart = rest.slice(2);
  return pathPart.startsWith('"') ? null : pathPart;
}

/** True when every payload line is recognized metadata (no hunk/content). */
function isMetadataOnlyPayload(buf) {
  const text = decodeUtf8(buf);
  if (text === null) return false;
  const lines = splitPayloadLines(text);
  if (lines.length === 0) return false;
  return lines.every((line) => classifyDiffLine(line) === "metadata");
}

// ---------------------------------------------------------------------------
// check collector
// ---------------------------------------------------------------------------

class Ctx {
  constructor(runRoot) {
    this.runRoot = runRoot;
    this.checks = [];
    this.exitCode = 0;
    this.aborted = false;
    this.primarySchema = null;
    this.cache = new Map();
    this.env = null;
    this.primary = null;
    this.capture = null;
    this.payloads = null;
  }

  push(name, ok, detail, code) {
    this.checks.push({ name, ok, detail, code });
    if (!ok) {
      if (code === 2) this.exitCode = 2;
      else if (this.exitCode === 0) this.exitCode = 1;
    }
    return ok;
  }

  ok(name, detail = "ok") {
    return this.push(name, true, detail, 0);
  }

  fail(name, detail, code = 1) {
    return this.push(name, false, detail, code);
  }

  /** Ordinary validation failure: record it and stop the pipeline. */
  stop(name, detail) {
    this.fail(name, detail, 1);
    this.aborted = true;
    return false;
  }

  /** Refusal: exit 2, or (with reason) ordinary failure + stop. */
  refuse(name, detail) {
    this.fail(name, detail, 2);
    this.aborted = true;
    return false;
  }
}

function finish(command, schema, checks, exitCode, reason) {
  const failed = checks.filter((c) => !c.ok);
  let summary;
  if (exitCode === 2) {
    const refusal = reason
      ?? failed.find((c) => c.code === 2)?.detail
      ?? failed[0]?.detail
      ?? "refused";
    summary = `REFUSE ${command}: ${refusal}`;
  } else if (exitCode === 1) {
    summary = `FAIL ${command}: ${failed.length} of ${checks.length} checks failed`;
  } else {
    summary = `PASS ${command}: ${checks.length} checks`;
  }
  const verdict = {
    ok: exitCode === 0,
    tool_version: TOOL_VERSION,
    schema,
    checks: checks.map((c) => ({ name: c.name, ok: c.ok, detail: c.detail })),
    summary,
  };
  process.stdout.write(`${JSON.stringify(verdict)}\n`);
  process.stderr.write(`verify: ${summary}\n`);
  process.exitCode = exitCode;
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function parseCli(argv) {
  if (argv.length !== 3) return { ok: false, reason: argv.length === 0 ? "missing command" : "unexpected arguments" };
  const [command, flag, value] = argv;
  if (!COMMANDS.has(command)) return { ok: false, reason: `unknown command: ${command}` };
  if (flag !== "--run") return { ok: false, reason: `expected --run, got: ${flag}` };
  if (!isNonEmptyString(value)) return { ok: false, reason: "missing run root" };
  return { ok: true, command, runRoot: value };
}

// ---------------------------------------------------------------------------
// safe artifact resolution + strict decoding
// ---------------------------------------------------------------------------

/**
 * Resolve a recorded ref against the run root (or a run-relative base such as
 * "claims") with lexical containment and realpath containment. Returns one of:
 *   {ok:true,abs,ref} {escape:true,ref} {missing:true,ref} {nonregular:true,ref}
 *   {unreadable:true,ref} {bad:true}
 * `ref` in messages is always a deterministic run-relative string.
 */
function resolveRef(ctx, ref, baseRel = "") {
  if (!isNonEmptyString(ref)) return { bad: true };
  const full = baseRel ? `${baseRel}/${ref}` : ref;
  if (path.isAbsolute(ref) || /^[A-Za-z][A-Za-z0-9+.-]*:/.test(ref)) return { escape: true, ref: full };
  const abs = path.resolve(ctx.runRoot, full);
  const relToRoot = path.relative(ctx.runRoot, abs);
  if (relToRoot === "" || relToRoot === ".." || relToRoot.startsWith(`..${path.sep}`) || path.isAbsolute(relToRoot)) {
    return { escape: true, ref: toPosix(full) };
  }
  let realRoot;
  try {
    realRoot = realpathSync(ctx.runRoot);
  } catch {
    realRoot = ctx.runRoot;
  }
  let realAbs;
  try {
    realAbs = realpathSync(abs);
  } catch (err) {
    const code = err?.code;
    if (code === "ENOENT" || code === "ENOTDIR" || code === "ELOOP") return { missing: true, ref: toPosix(full) };
    return { unreadable: true, ref: toPosix(full) };
  }
  const relReal = path.relative(realRoot, realAbs);
  if (relReal === ".." || relReal.startsWith(`..${path.sep}`) || path.isAbsolute(relReal)) {
    return { escape: true, ref: toPosix(full) };
  }
  try {
    if (!statSync(realAbs).isFile()) return { nonregular: true, ref: toPosix(full) };
  } catch {
    return { unreadable: true, ref: toPosix(full) };
  }
  return { ok: true, abs: realAbs, ref: toPosix(full) };
}

/** Read one artifact (bytes cached once per resolved file). Emits failure checks. */
function readArtifact(ctx, ref, baseRel = "") {
  const resolved = resolveRef(ctx, ref, baseRel);
  if (resolved.bad) {
    ctx.stop("artifact.path", `artifact path invalid: ${q(ref)}`);
    return null;
  }
  if (resolved.escape) {
    ctx.refuse("artifact.path", `artifact path escapes run root: ${resolved.ref}`);
    return null;
  }
  if (resolved.nonregular) {
    ctx.stop("artifact.type", `artifact is not a regular file: ${resolved.ref}`);
    return null;
  }
  if (resolved.missing || resolved.unreadable) {
    ctx.stop("artifact.read", `cannot read artifact: ${resolved.ref}`);
    return null;
  }
  const cached = ctx.cache.get(resolved.abs);
  if (cached) return cached;
  try {
    const buf = readFileSync(resolved.abs);
    ctx.cache.set(resolved.abs, buf);
    return buf;
  } catch {
    ctx.stop("artifact.read", `cannot read artifact: ${resolved.ref}`);
    return null;
  }
}

function parseJsonArtifact(ctx, ref, buf) {
  if (hasUtf8Bom(buf)) {
    ctx.stop("artifact.json", `invalid JSON: ${q(ref)}`);
    return null;
  }
  const text = decodeUtf8(buf);
  if (text === null) {
    ctx.stop("artifact.json", `invalid UTF-8: ${q(ref)}`);
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    ctx.stop("artifact.json", `invalid JSON: ${q(ref)}`);
    return null;
  }
}

/**
 * Parse a JSON artifact and immediately require a non-null plain object top
 * level (F14): falsy/non-object JSON literals can never silently skip the
 * artifact's checks.
 */
function parseJsonObjectArtifact(ctx, ref, buf) {
  const value = parseJsonArtifact(ctx, ref, buf);
  if (ctx.aborted) return null;
  if (!isPlainObject(value)) {
    ctx.stop("shape", "invalid field: / expected object");
    return null;
  }
  return value;
}

/** Parse a JSON artifact and immediately require an array top level (F14). */
function parseJsonArrayArtifact(ctx, ref, buf) {
  const value = parseJsonArtifact(ctx, ref, buf);
  if (ctx.aborted) return null;
  if (!Array.isArray(value)) {
    ctx.stop("shape", "invalid field: / expected array");
    return null;
  }
  return value;
}

function parseJsonlArtifact(ctx, ref, buf) {
  if (hasUtf8Bom(buf)) {
    ctx.stop("artifact.jsonl", `invalid JSONL: ${q(ref)}:1`);
    return null;
  }
  const text = decodeUtf8(buf);
  if (text === null) {
    ctx.stop("artifact.jsonl", `invalid UTF-8: ${q(ref)}`);
    return null;
  }
  const lines = text.split("\n");
  if (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();
  const rows = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim() === "") {
      ctx.stop("artifact.jsonl", `invalid JSONL: ${q(ref)}:${i + 1}`);
      return null;
    }
    try {
      rows.push(JSON.parse(line));
    } catch {
      ctx.stop("artifact.jsonl", `invalid JSONL: ${q(ref)}:${i + 1}`);
      return null;
    }
  }
  return rows;
}

/** SHA-256 exact-bytes pin check; emits one check per pinned artifact. */
function checkPin(ctx, ref, buf, pin) {
  if (pin === undefined || pin === null || pin === "") {
    ctx.fail("artifact.sha256", `sha256 pin missing: ${q(ref)}`);
    return false;
  }
  if (typeof pin !== "string" || pin !== sha256(buf)) {
    ctx.fail("artifact.sha256", `sha256 mismatch: ${q(ref)}`);
    return false;
  }
  ctx.ok("artifact.sha256", ref);
  return true;
}

// ---------------------------------------------------------------------------
// envelope + shared schema/verifier checks
// ---------------------------------------------------------------------------

function loadEnvelope(ctx) {
  const buf = readArtifact(ctx, ENVELOPE_REF);
  if (!buf || ctx.aborted) return null;
  const env = parseJsonObjectArtifact(ctx, ENVELOPE_REF, buf);
  if (!env || ctx.aborted) return null;
  const sv = env.schema_version;
  if (!isNonEmptyString(sv)) {
    ctx.stop("schema", "invalid field: /schema_version expected nonempty string");
    return null;
  }
  if (sv !== "run-verification/1") {
    ctx.refuse("schema", `unsupported schema_version: ${q(sv)}`);
    return null;
  }
  ctx.ok("schema", sv);
  if (!isPlainObject(env.verifier)) {
    ctx.stop("shape", "invalid field: /verifier expected object");
    return null;
  }
  ctx.env = env;
  return env;
}

function checkVerifier(ctx, env) {
  const verifier = env.verifier;
  if (verifier.path !== undefined && !isNonEmptyString(verifier.path)) {
    ctx.stop("shape", "invalid field: /verifier/path expected nonempty string");
    return false;
  }
  let ok = true;
  let ownSha = null;
  try {
    ownSha = sha256(readFileSync(VERIFY_PATH));
  } catch {
    ownSha = null;
  }
  if (verifier.sha256 !== ownSha) {
    ctx.fail("verifier.identity", "verifier sha256 mismatch");
    ok = false;
  } else {
    ctx.ok("verifier.identity", "ok");
  }
  if (verifier.tool_version !== TOOL_VERSION) {
    ctx.fail("verifier.version", "verifier tool_version mismatch");
    ok = false;
  } else {
    ctx.ok("verifier.version", TOOL_VERSION);
  }
  if (!ok) ctx.aborted = true;
  return ok;
}

/**
 * Check an embedded envelope schema_version declaration. Unknown => refusal;
 * supported but other family => wrong-kind refusal; absent => tolerated here
 * (agreement with the artifact is checked after discovery).
 */
function declaredSchema(ctx, obj, pointer, family) {
  if (!isPlainObject(obj)) {
    ctx.stop("shape", `invalid field: ${pointer} expected object`);
    return undefined;
  }
  const sv = obj.schema_version;
  if (sv === undefined) return undefined;
  if (!isNonEmptyString(sv)) {
    ctx.stop("schema", `invalid field: ${pointer}/schema_version expected nonempty string`);
    return undefined;
  }
  const entry = REGISTRY.get(sv);
  if (!entry) {
    ctx.refuse("schema", `unsupported schema_version: ${q(sv)}`);
    return undefined;
  }
  if (entry.family !== family) {
    ctx.refuse("artifact.discovery", `wrong schema kind: ${q(sv)} for ${family}`);
    return undefined;
  }
  return sv;
}

// ---------------------------------------------------------------------------
// primary artifact discovery + load
// ---------------------------------------------------------------------------

function listDirCandidates(ctx, dirRel, pattern) {
  let entries;
  try {
    entries = readdirSync(path.join(ctx.runRoot, dirRel), { withFileTypes: true });
  } catch {
    return [];
  }
  const out = [];
  for (const entry of entries) {
    if (!(entry.isFile() || entry.isSymbolicLink())) continue;
    if (!pattern.test(entry.name)) continue;
    out.push(`${dirRel}/${entry.name}`);
  }
  out.sort();
  return out;
}

function discoverPrimary(ctx, command, env) {
  const pinEntry = env[PRIMARY_PIN_FIELD[command]];
  const envRef = isPlainObject(pinEntry) && isNonEmptyString(pinEntry.ref) ? pinEntry.ref : null;
  let candidates;
  if (command === "claims") {
    candidates = listDirCandidates(ctx, "claims", /^claims-draft.*\.json$/);
  } else if (command === "join") {
    candidates = listDirCandidates(ctx, "join", /^join-draft.*\.json$/);
  } else {
    candidates = [];
    for (const rel of ["units/units2/manifest.json", "units2/manifest.json"]) {
      try {
        if (statSync(path.join(ctx.runRoot, rel)).isFile()) candidates.push(rel);
      } catch {
        /* absent */
      }
    }
  }
  if (candidates.length === 0) {
    ctx.stop("artifact.discovery", `artifact missing: ${PRIMARY_KIND[command]}`);
    return null;
  }
  if (candidates.length > 1) {
    ctx.refuse("artifact.discovery", `ambiguous artifact: ${PRIMARY_KIND[command]}`);
    return null;
  }
  const ref = candidates[0];
  if (envRef && envRef !== ref) {
    ctx.refuse("artifact.discovery", `artifact ref mismatch: ${q(envRef)} != ${q(ref)}`);
    return null;
  }
  ctx.ok("artifact.discovery", ref);
  return ref;
}

/** Read + parse the primary artifact, dispatch schema, verify sha pin. */
function loadPrimary(ctx, command, ref) {
  const pinEntry = ctx.env[PRIMARY_PIN_FIELD[command]];
  const pinRef = isPlainObject(pinEntry) && isNonEmptyString(pinEntry.ref) ? pinEntry.ref : ref;
  const buf = readArtifact(ctx, ref);
  if (!buf || ctx.aborted) return null;
  const obj = parseJsonObjectArtifact(ctx, ref, buf);
  if (!obj || ctx.aborted) return null;
  const sv = obj.schema_version;
  if (!isNonEmptyString(sv)) {
    ctx.stop("schema", "invalid field: /schema_version expected nonempty string");
    return null;
  }
  const entry = REGISTRY.get(sv);
  if (!entry) {
    ctx.refuse("schema", `unsupported schema_version: ${q(sv)}`);
    return null;
  }
  if (entry.family !== command) {
    ctx.refuse("artifact.discovery", `wrong schema kind: ${q(sv)} for ${command}`);
    return null;
  }
  if (isPlainObject(pinEntry) && isNonEmptyString(pinEntry.schema_version) && pinEntry.schema_version !== sv) {
    ctx.stop("schema", `schema_version mismatch: ${q(pinEntry.schema_version)} != ${q(sv)}`);
    return null;
  }
  ctx.primarySchema = sv;
  ctx.ok("schema", sv);
  const pin = isPlainObject(pinEntry) ? pinEntry.sha256 : undefined;
  checkPin(ctx, pinRef, buf, pin);
  ctx.primary = { ref, obj, buf };
  return { ref, obj, buf };
}

// ---------------------------------------------------------------------------
// shared identity check
// ---------------------------------------------------------------------------

function checkIdentity(ctx, env, primary, capture) {
  const fields = ["run", "review_state", "subject_oid", "base_oid"];
  for (const field of fields) {
    if (primary[field] !== env[field]) {
      ctx.fail("identity", `identity mismatch: /${field}`);
      return;
    }
    if (capture[field] !== env[field]) {
      ctx.fail("identity", `identity mismatch: /${field}`);
      return;
    }
  }
  if (capture.cure_light_source_head_oid !== env.cure_light_source_head_oid) {
    ctx.fail("identity", "identity mismatch: /cure_light_source_head_oid");
    return;
  }
  ctx.ok("identity", "ok");
}

/**
 * Load and validate the capture manifest evidence common to claims/units:
 * envelope entry shape/ref, optional schema dispatch (capture family), exact
 * bytes and pin. The envelope entry is REQUIRED — there is no silent default
 * ref, and a present entry without sha256 fails the pin check.
 * Returns {ref, capture} or null (failures already recorded).
 */
function loadCapture(ctx, env) {
  if (!isPlainObject(env.capture_manifest)) {
    ctx.stop("shape", "invalid field: /capture_manifest expected object");
    return null;
  }
  const captureEntry = env.capture_manifest;
  if (!isNonEmptyString(captureEntry.ref)) {
    ctx.stop("shape", "invalid field: /capture_manifest/ref expected nonempty string");
    return null;
  }
  if (
    captureEntry.schema_version !== undefined
    && !dispatchCaptureSchema(ctx, captureEntry.schema_version, "/capture_manifest/schema_version")
  ) {
    return null;
  }
  const captureRef = captureEntry.ref;
  const captureBuf = readArtifact(ctx, captureRef);
  if (!captureBuf || ctx.aborted) return null;
  const capture = parseJsonObjectArtifact(ctx, captureRef, captureBuf);
  if (!capture || ctx.aborted) return null;
  if (
    capture.schema_version !== undefined
    && !dispatchCaptureSchema(ctx, capture.schema_version, "/schema_version")
  ) {
    return null;
  }
  checkPin(ctx, captureRef, captureBuf, captureEntry.sha256);
  return { ref: captureRef, capture };
}

/**
 * Capture manifests own a (currently unregistered) capture family: an unknown
 * schema_version refuses 2, and any supported schema is a wrong-kind refusal
 * rather than an accepted capture identity.
 */
function dispatchCaptureSchema(ctx, sv, pointer) {
  if (!isNonEmptyString(sv)) {
    ctx.stop("schema", `invalid field: ${pointer} expected nonempty string`);
    return false;
  }
  const entry = REGISTRY.get(sv);
  if (!entry) {
    ctx.refuse("schema", `unsupported schema_version: ${q(sv)}`);
    return false;
  }
  if (entry.family !== "capture") {
    ctx.refuse("artifact.discovery", `wrong schema kind: ${q(sv)} for capture`);
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// claims-draft/3 — C1..C9
// ---------------------------------------------------------------------------

// C1: strict shape/type validation (no coercion). First failure wins.
function validateClaimsShape(claims) {
  const bad = (pointer, type) => `invalid field: ${pointer} expected ${type}`;
  if (!isPlainObject(claims)) return bad("/", "object");
  for (const field of ["run", "review_state", "subject_oid", "base_oid"]) {
    if (!isNonEmptyString(claims[field])) return bad(`/${field}`, "nonempty string");
  }
  for (const field of ["sources", "claims", "nonclaims", "conflicts", "notes", "missing_source_candidates"]) {
    if (!Array.isArray(claims[field])) return bad(`/${field}`, "array");
  }

  for (let i = 0; i < claims.sources.length; i++) {
    const s = claims.sources[i];
    const p = `/sources/${i}`;
    if (!isPlainObject(s)) return bad(p, "object");
    for (const field of ["source_ref", "locator", "path", "role", "sha256"]) {
      if (!isNonEmptyString(s[field])) return bad(`${p}/${field}`, "nonempty string");
    }
    if (!isNonNegInt(s.byte_length)) return bad(`${p}/byte_length`, "nonnegative integer");
    if (s.blob_subject !== undefined && !isNonEmptyString(s.blob_subject)) return bad(`${p}/blob_subject`, "nonempty string");
  }

  for (let i = 0; i < claims.claims.length; i++) {
    const c = claims.claims[i];
    const p = `/claims/${i}`;
    if (!isPlainObject(c)) return bad(p, "object");
    for (const field of ["id", "statement", "source_ref", "quote"]) {
      if (!isNonEmptyString(c[field])) return bad(`${p}/${field}`, "nonempty string");
    }
    if (!Array.isArray(c.also_in)) return bad(`${p}/also_in`, "array");
    for (let j = 0; j < c.also_in.length; j++) {
      if (!isNonEmptyString(c.also_in[j])) return bad(`${p}/also_in/${j}`, "nonempty string");
    }
  }

  for (let i = 0; i < claims.nonclaims.length; i++) {
    const n = claims.nonclaims[i];
    const p = `/nonclaims/${i}`;
    if (!isPlainObject(n)) return bad(p, "object");
    for (const field of ["id", "statement", "source_ref", "quote", "reason"]) {
      if (!isNonEmptyString(n[field])) return bad(`${p}/${field}`, "nonempty string");
    }
    if (n.also_in !== undefined) {
      if (!Array.isArray(n.also_in)) return bad(`${p}/also_in`, "array");
      for (let j = 0; j < n.also_in.length; j++) {
        if (!isNonEmptyString(n.also_in[j])) return bad(`${p}/also_in/${j}`, "nonempty string");
      }
    }
  }

  for (let i = 0; i < claims.conflicts.length; i++) {
    const x = claims.conflicts[i];
    const p = `/conflicts/${i}`;
    if (!isPlainObject(x)) return bad(p, "object");
    for (const field of ["id", "kind", "materiality", "precedence", "witness", "reasoning"]) {
      if (!isNonEmptyString(x[field])) return bad(`${p}/${field}`, "nonempty string");
    }
    if (!Array.isArray(x.quotes)) return bad(`${p}/quotes`, "array");
    for (let j = 0; j < x.quotes.length; j++) {
      const r = x.quotes[j];
      const rp = `${p}/quotes/${j}`;
      if (!isPlainObject(r)) return bad(rp, "object");
      if (!isNonEmptyString(r.source_ref)) return bad(`${rp}/source_ref`, "nonempty string");
      if (!isNonEmptyString(r.quote)) return bad(`${rp}/quote`, "nonempty string");
      if (r.offset_bytes !== null && !isNonNegInt(r.offset_bytes)) return bad(`${rp}/offset_bytes`, "null or nonnegative integer");
    }
    if (!Array.isArray(x.affected_claim_ids)) return bad(`${p}/affected_claim_ids`, "array");
    for (let j = 0; j < x.affected_claim_ids.length; j++) {
      if (!isNonEmptyString(x.affected_claim_ids[j])) return bad(`${p}/affected_claim_ids/${j}`, "nonempty string");
    }
  }

  for (let i = 0; i < claims.notes.length; i++) {
    const n = claims.notes[i];
    const p = `/notes/${i}`;
    if (!isPlainObject(n)) return bad(p, "object");
    if (!isNonEmptyString(n.note)) return bad(`${p}/note`, "nonempty string");
    if (n.source_ref !== undefined && !isNonEmptyString(n.source_ref)) return bad(`${p}/source_ref`, "nonempty string");
    if (n.quote !== undefined && !isNonEmptyString(n.quote)) return bad(`${p}/quote`, "nonempty string");
  }

  for (let i = 0; i < claims.missing_source_candidates.length; i++) {
    const c = claims.missing_source_candidates[i];
    const p = `/missing_source_candidates/${i}`;
    if (!isPlainObject(c)) return bad(p, "object");
    for (const field of ["resource", "reference_quote", "why_it_matters"]) {
      if (!isNonEmptyString(c[field])) return bad(`${p}/${field}`, "nonempty string");
    }
    if (!Array.isArray(c.affected_claim_ids)) return bad(`${p}/affected_claim_ids`, "array");
    for (let j = 0; j < c.affected_claim_ids.length; j++) {
      if (!isNonEmptyString(c.affected_claim_ids[j])) return bad(`${p}/affected_claim_ids/${j}`, "nonempty string");
    }
  }

  if (claims.source_consistency !== undefined) {
    const sc = claims.source_consistency;
    if (!isPlainObject(sc)) return bad("/source_consistency", "object");
    if (sc.status !== undefined && !isNonEmptyString(sc.status)) return bad("/source_consistency/status", "nonempty string");
    if (sc.records !== undefined) {
      if (!Array.isArray(sc.records)) return bad("/source_consistency/records", "array");
      for (let i = 0; i < sc.records.length; i++) {
        const r = sc.records[i];
        if (!isPlainObject(r)) return bad(`/source_consistency/records/${i}`, "object");
        if (!isNonEmptyString(r.id)) return bad(`/source_consistency/records/${i}/id`, "nonempty string");
      }
    }
    if (sc.notes !== undefined && !isNonEmptyString(sc.notes)) return bad("/source_consistency/notes", "nonempty string");
  }

  return null;
}

function checkClaimsShape(ctx, claims) {
  const failure = validateClaimsShape(claims);
  if (failure) {
    ctx.stop("shape", failure);
    return false;
  }
  ctx.ok("shape", "ok");
  return true;
}

// C2: ordered uniqueness of claim ids, nonclaim ids, and the claim/nonclaim namespace.
function checkClaimIds(ctx, claims) {
  const claimSeen = new Set();
  for (const claim of claims.claims) {
    if (claimSeen.has(claim.id)) {
      ctx.fail("claims.ids", `duplicate claim id: ${q(claim.id)}`);
      return;
    }
    claimSeen.add(claim.id);
  }
  const nonclaimSeen = new Set();
  for (const nonclaim of claims.nonclaims) {
    if (nonclaimSeen.has(nonclaim.id)) {
      ctx.fail("claims.ids", `duplicate nonclaim id: ${q(nonclaim.id)}`);
      return;
    }
    nonclaimSeen.add(nonclaim.id);
  }
  for (const nonclaim of claims.nonclaims) {
    if (claimSeen.has(nonclaim.id)) {
      ctx.fail("claims.ids", `claim/nonclaim id collision: ${q(nonclaim.id)}`);
      return;
    }
  }
  const conflictSeen = new Set();
  for (const conflict of claims.conflicts) {
    if (conflictSeen.has(conflict.id)) {
      ctx.fail("claims.ids", `duplicate conflict id: ${q(conflict.id)}`);
      return;
    }
    conflictSeen.add(conflict.id);
  }
  ctx.ok("claims.ids", "ok");
}

// Resolve and read every declared source in both record families, once.
function resolveSourceBytes(ctx, claims, capture) {
  const claimBytes = new Map();
  const titleBytes = new Map();
  const capturedRefs = new Set();
  for (const source of claims.sources) {
    const buf = readArtifact(ctx, source.path);
    if (!buf || ctx.aborted) return null;
    if (!claimBytes.has(source.source_ref)) claimBytes.set(source.source_ref, buf);
    capturedRefs.add(source.source_ref);
  }
  for (const source of capture.sources) {
    const buf = readArtifact(ctx, source.path, "claims");
    if (!buf || ctx.aborted) return null;
    capturedRefs.add(source.locator);
    if (isNonEmptyString(source.title_path)) {
      const title = readArtifact(ctx, source.title_path, "claims");
      if (!title || ctx.aborted) return null;
      titleBytes.set(source.locator, title);
    }
  }
  return { claimBytes, titleBytes, capturedRefs };
}

// C3: source refs unique + captured, declared byte_length/sha256 equal capture
// records and actual bytes, blob_subject agreement, declared title bytes.
function checkClaimSources(ctx, claims, capture, sources) {
  const captureByLocator = new Map();
  let duplicateCaptureRef = null;
  for (const source of capture.sources) {
    if (captureByLocator.has(source.locator)) duplicateCaptureRef ??= source.locator;
    captureByLocator.set(source.locator, source);
  }
  const seen = new Set();
  let failure = null;
  for (const source of claims.sources) {
    if (failure) break;
    if (seen.has(source.source_ref)) {
      failure = `duplicate source ref: ${q(source.source_ref)}`;
      continue;
    }
    seen.add(source.source_ref);
    const captured = captureByLocator.get(source.source_ref);
    if (!captured) {
      failure = `source ref not captured: ${q(source.source_ref)}`;
      continue;
    }
    const actual = sources.claimBytes.get(source.source_ref);
    if (!actual) continue;
    const actualSha = sha256(actual);
    if (source.byte_length !== captured.capture_byte_length || source.byte_length !== actual.length || captured.capture_byte_length !== actual.length) {
      failure = `source byte_length mismatch: ${q(source.source_ref)}`;
      continue;
    }
    if (source.sha256 !== captured.capture_sha256 || source.sha256 !== actualSha || captured.capture_sha256 !== actualSha) {
      failure = `source sha256 mismatch: ${q(source.source_ref)}`;
      continue;
    }
    if (source.blob_subject !== undefined && captured.blob_subject !== undefined && source.blob_subject !== captured.blob_subject) {
      failure = `source blob_subject mismatch: ${q(source.source_ref)}`;
      continue;
    }
    if (isNonEmptyString(captured.title_path)) {
      const title = sources.titleBytes.get(source.source_ref);
      if (title) {
        if (captured.title_byte_length !== title.length) {
          failure = `source title byte_length mismatch: ${q(source.source_ref)}`;
          continue;
        }
        if (captured.title_sha256 !== sha256(title)) {
          failure = `source title sha256 mismatch: ${q(source.source_ref)}`;
          continue;
        }
      }
    }
  }
  if (!failure && duplicateCaptureRef) failure = `duplicate source ref: ${q(duplicateCaptureRef)}`;
  if (failure) ctx.fail("claims.sources", failure);
  else ctx.ok("claims.sources", "ok");
}

// C4: every claim/nonclaim quote is a verbatim byte substring of its declared source.
function checkQuotes(ctx, claims, sourceBytes) {
  const items = [...claims.claims, ...claims.nonclaims];
  for (const item of items) {
    const source = sourceBytes.get(item.source_ref);
    if (!source) {
      ctx.fail("claims.quote", `unknown source ref: ${q(item.source_ref)}`);
      return;
    }
    if (!source.includes(Buffer.from(item.quote, "utf8"))) {
      ctx.fail("claims.quote", `quote not in source: ${q(item.id)}`);
      return;
    }
  }
  ctx.ok("claims.quote", "ok");
}

// C5: also_in refs are unique captured source refs (claims required, nonclaims optional).
function checkAlsoIn(ctx, claims, capturedRefs) {
  const items = [
    ...claims.claims.map((c) => ({ id: c.id, refs: c.also_in })),
    ...claims.nonclaims.filter((n) => n.also_in !== undefined).map((n) => ({ id: n.id, refs: n.also_in })),
  ];
  for (const { id, refs } of items) {
    const seen = new Set();
    for (const ref of refs) {
      if (seen.has(ref)) {
        ctx.fail("claims.also_in", `duplicate also_in ref: ${q(id)} -> ${q(ref)}`);
        return;
      }
      seen.add(ref);
      if (!capturedRefs.has(ref)) {
        ctx.fail("claims.also_in", `also_in ref not found: ${q(id)} -> ${q(ref)}`);
        return;
      }
    }
  }
  ctx.ok("claims.also_in", "ok");
}

// C6: conflict structure, affected-id resolution, quote substrings, exact
// non-null UTF-8 byte offsets, and source_consistency record resolution.
// Structural enums only — no materiality/precedence semantics.
function checkConflicts(ctx, claims, sourceBytes, claimIds) {
  const conflictIds = new Set();
  for (const conflict of claims.conflicts) {
    conflictIds.add(conflict.id);
    if (conflict.kind !== "within-source" && conflict.kind !== "cross-source") {
      ctx.fail("claims.conflicts", `invalid conflict kind: ${q(conflict.id)}: ${q(conflict.kind)}`);
      return;
    }
    if (conflict.materiality !== "material" && conflict.materiality !== "non-material") {
      ctx.fail("claims.conflicts", `invalid conflict materiality: ${q(conflict.id)}: ${q(conflict.materiality)}`);
      return;
    }
    for (const id of conflict.affected_claim_ids) {
      if (!claimIds.has(id)) {
        ctx.fail("claims.conflicts", `affected claim id not found: ${q(conflict.id)} -> ${q(id)}`);
        return;
      }
    }
    for (const quoteRecord of conflict.quotes) {
      const source = sourceBytes.get(quoteRecord.source_ref);
      if (!source) {
        ctx.fail("claims.conflicts", `unknown source ref: ${q(quoteRecord.source_ref)}`);
        return;
      }
      const offset = source.indexOf(Buffer.from(quoteRecord.quote, "utf8"));
      if (offset < 0) {
        ctx.fail("claims.conflicts", `quote not in source: ${q(conflict.id)}`);
        return;
      }
      if (quoteRecord.offset_bytes !== null && offset !== quoteRecord.offset_bytes) {
        ctx.fail("claims.conflicts", `quote offset mismatch: ${q(conflict.id)}`);
        return;
      }
    }
  }
  const records = claims.source_consistency?.records;
  if (Array.isArray(records)) {
    for (const record of records) {
      if (!conflictIds.has(record.id)) {
        ctx.fail("claims.conflicts", `consistency record not found: ${q(record.id)}`);
        return;
      }
    }
  }
  ctx.ok("claims.conflicts", "ok");
}

// C7: notes stay opaque prose; optional quote+source_ref must come as a pair.
function checkNotes(ctx, claims, sourceBytes) {
  for (let i = 0; i < claims.notes.length; i++) {
    const note = claims.notes[i];
    const hasSource = note.source_ref !== undefined;
    const hasQuote = note.quote !== undefined;
    if (hasSource !== hasQuote) {
      ctx.fail("claims.notes", hasQuote ? `note quote without source_ref: /notes/${i}` : `note source_ref without quote: /notes/${i}`);
      return;
    }
    if (hasSource) {
      const source = sourceBytes.get(note.source_ref);
      if (!source) {
        ctx.fail("claims.notes", `unknown source ref: ${q(note.source_ref)}`);
        return;
      }
      if (!source.includes(Buffer.from(note.quote, "utf8"))) {
        ctx.fail("claims.notes", `note quote not in source: /notes/${i}`);
        return;
      }
    }
  }
  ctx.ok("claims.notes", "ok");
}

// C8: missing-source candidates — reference_quote occurs in >=1 captured
// source; affected_claim_ids resolve. No authority granted to the resource.
function checkCandidates(ctx, claims, sourceBytes) {
  const sourceList = [...sourceBytes.values()];
  const claimIds = new Set(claims.claims.map((c) => c.id));
  for (let i = 0; i < claims.missing_source_candidates.length; i++) {
    const candidate = claims.missing_source_candidates[i];
    const quote = Buffer.from(candidate.reference_quote, "utf8");
    if (!sourceList.some((source) => source.includes(quote))) {
      ctx.fail("claims.candidates", `candidate quote not in captured sources: ${i}`);
      return;
    }
    const seenIds = new Set();
    for (const id of candidate.affected_claim_ids) {
      if (seenIds.has(id)) {
        ctx.fail("claims.candidates", `duplicate candidate affected claim id: ${i} -> ${q(id)}`);
        return;
      }
      seenIds.add(id);
      if (!claimIds.has(id)) {
        ctx.fail("claims.candidates", `candidate affected claim id not found: ${i} -> ${q(id)}`);
        return;
      }
    }
  }
  ctx.ok("claims.candidates", "ok");
}

// C9: computed counts are always reported; an optional envelope claims_counts
// object is validated when declared, never required.
function checkCounts(ctx, claims, env) {
  const counts = {
    claims: claims.claims.length,
    nonclaims: claims.nonclaims.length,
    conflicts: claims.conflicts.length,
    notes: claims.notes.length,
    missing_source_candidates: claims.missing_source_candidates.length,
  };
  const declared = env.claims_counts;
  if (declared !== undefined && !isPlainObject(declared)) {
    ctx.stop("shape", "invalid field: /claims_counts expected object");
    return;
  }
  if (isPlainObject(declared)) {
    for (const field of Object.keys(counts)) {
      if (declared[field] !== undefined && declared[field] !== counts[field]) {
        ctx.fail("claims.counts", `claims count mismatch: ${field}`);
        return;
      }
    }
  }
  ctx.ok(
    "claims.counts",
    `claims=${counts.claims} nonclaims=${counts.nonclaims} conflicts=${counts.conflicts} notes=${counts.notes} missing_source_candidates=${counts.missing_source_candidates}`,
  );
}

function runClaims(ctx) {
  const env = loadEnvelope(ctx);
  if (!env || ctx.aborted) return;
  if (!checkVerifier(ctx, env)) return;
  declaredSchema(ctx, env.claims_draft, "/claims_draft", "claims");
  if (ctx.aborted) return;
  const ref = discoverPrimary(ctx, "claims", env);
  if (!ref || ctx.aborted) return;
  const primary = loadPrimary(ctx, "claims", ref);
  if (!primary || ctx.aborted) return;
  const claims = primary.obj;

  const captureLoad = loadCapture(ctx, env);
  if (!captureLoad || ctx.aborted) return;
  const capture = captureLoad.capture;
  ctx.capture = capture;
  if (!Array.isArray(capture.sources)) {
    ctx.stop("shape", "invalid field: /sources expected array");
    return;
  }

  if (!checkClaimsShape(ctx, claims)) return;
  checkIdentity(ctx, env, claims, capture);
  const sources = resolveSourceBytes(ctx, claims, capture);
  if (!sources || ctx.aborted) return;

  checkClaimIds(ctx, claims);
  checkClaimSources(ctx, claims, capture, sources);
  checkQuotes(ctx, claims, sources.claimBytes);
  checkAlsoIn(ctx, claims, sources.capturedRefs);
  checkConflicts(ctx, claims, sources.claimBytes, new Set(claims.claims.map((c) => c.id)));
  checkNotes(ctx, claims, sources.claimBytes);
  checkCandidates(ctx, claims, sources.claimBytes);
  checkCounts(ctx, claims, env);
}

// ---------------------------------------------------------------------------
// units — code-units-sim/2 (U1..U7)
//
// Join (join-draft/1) is implemented further below: J1–J12 checks are live.
// ---------------------------------------------------------------------------

// U1 shape: strict types for recipe/identity/counts/units (no coercion).
function validateUnitsShape(manifest) {
  const bad = (pointer, type) => `invalid field: ${pointer} expected ${type}`;
  if (!isPlainObject(manifest)) return bad("/", "object");

  if (!isPlainObject(manifest.recipe)) return bad("/recipe", "object");
  if (!isNonEmptyString(manifest.recipe.chunker)) return bad("/recipe/chunker", "nonempty string");
  for (const field of ["target_bytes", "ceiling_bytes", "context"]) {
    if (!isNonNegInt(manifest.recipe[field])) return bad(`/recipe/${field}`, "nonnegative integer");
  }
  if (typeof manifest.recipe.block_preference !== "boolean") return bad("/recipe/block_preference", "boolean");

  if (!isPlainObject(manifest.identity)) return bad("/identity", "object");
  for (const field of ["repo", "base_ref", "subject_ref", "base_oid", "subject_oid"]) {
    if (!isNonEmptyString(manifest.identity[field])) return bad(`/identity/${field}`, "nonempty string");
  }

  if (!isPlainObject(manifest.counts)) return bad("/counts", "object");
  for (const field of ["units", "files", "line_split_units", "total_bytes"]) {
    if (!isNonNegInt(manifest.counts[field])) return bad(`/counts/${field}`, "nonnegative integer");
  }

  if (!Array.isArray(manifest.units)) return bad("/units", "array");
  for (let i = 0; i < manifest.units.length; i++) {
    const unit = manifest.units[i];
    const p = `/units/${i}`;
    if (!isPlainObject(unit)) return bad(p, "object");
    for (const field of ["unit_id", "file", "path", "boundary_kind"]) {
      if (!isNonEmptyString(unit[field])) return bad(`${p}/${field}`, "nonempty string");
    }
    for (const field of ["hunk_count", "byte_len", "blocks"]) {
      if (!isNonNegInt(unit[field])) return bad(`${p}/${field}`, "nonnegative integer");
    }
    if (!Array.isArray(unit.ranges)) return bad(`${p}/ranges`, "array");
    for (let j = 0; j < unit.ranges.length; j++) {
      const range = unit.ranges[j];
      const rp = `${p}/ranges/${j}`;
      if (!isPlainObject(range)) return bad(rp, "object");
      for (const field of ["old_start", "old_count", "new_start", "new_count"]) {
        if (!isNonNegInt(range[field])) return bad(`${rp}/${field}`, "nonnegative integer");
      }
    }
  }
  return null;
}

// Envelope slice required by `units`: chunker provenance (lexical only — the
// fixture pin is synthetic and never re-hashed against live chunker bytes) and
// the unit payload pin table.
function checkUnitsEnvelopeShape(ctx, env) {
  if (!isPlainObject(env.chunker)) return ctx.stop("shape", "invalid field: /chunker expected object");
  if (!isNonEmptyString(env.chunker.path)) return ctx.stop("shape", "invalid field: /chunker/path expected nonempty string");
  if (!isNonEmptyString(env.chunker.sha256) || !/^[0-9a-f]{64}$/.test(env.chunker.sha256)) {
    return ctx.stop("shape", "invalid field: /chunker/sha256 expected sha256 hex string");
  }
  if (!isPlainObject(env.chunker.recipe)) return ctx.stop("shape", "invalid field: /chunker/recipe expected object");
  if (!isNonEmptyString(env.chunker.cure_light_source_head_oid)) {
    return ctx.stop("shape", "invalid field: /chunker/cure_light_source_head_oid expected nonempty string");
  }
  if (!Array.isArray(env.unit_payloads)) return ctx.stop("shape", "invalid field: /unit_payloads expected array");
  for (let i = 0; i < env.unit_payloads.length; i++) {
    const pin = env.unit_payloads[i];
    const p = `/unit_payloads/${i}`;
    if (!isPlainObject(pin)) return ctx.stop("shape", `invalid field: ${p} expected object`);
    if (!isNonEmptyString(pin.unit_id)) return ctx.stop("shape", `invalid field: ${p}/unit_id expected nonempty string`);
    if (!isNonEmptyString(pin.ref)) return ctx.stop("shape", `invalid field: ${p}/ref expected nonempty string`);
  }
  return true;
}

// U2 identity/recipe/engine provenance (no subject read, no chunker execution).
function checkUnitsIdentity(ctx, env, manifest, capture) {
  const id = manifest.identity;
  const fail = (detail) => {
    ctx.fail("units.identity", detail);
    return false;
  };
  if (env.base_oid !== id.base_oid || capture.base_oid !== id.base_oid) return fail("identity mismatch: /identity/base_oid");
  if (env.subject_oid !== id.subject_oid || capture.subject_oid !== id.subject_oid) return fail("identity mismatch: /identity/subject_oid");
  if (id.base_ref !== id.base_oid) return fail("identity mismatch: /identity/base_ref");
  if (id.subject_ref !== id.subject_oid) return fail("identity mismatch: /identity/subject_ref");
  if (env.chunker.cure_light_source_head_oid !== env.cure_light_source_head_oid) {
    return fail("identity mismatch: /chunker/cure_light_source_head_oid");
  }
  if (capture.cure_light_source_head_oid !== env.cure_light_source_head_oid) {
    return fail("identity mismatch: /cure_light_source_head_oid");
  }
  if (env.run !== capture.run) return fail("identity mismatch: /run");
  if (env.review_state !== capture.review_state) return fail("identity mismatch: /review_state");
  for (const field of Object.keys(UNITS_RECIPE)) {
    if (manifest.recipe[field] !== UNITS_RECIPE[field]) return fail(`chunker recipe mismatch: /recipe/${field}`);
  }
  for (const field of Object.keys(UNITS_RECIPE)) {
    if (env.chunker.recipe[field] !== manifest.recipe[field]) return fail(`chunker recipe mismatch: /chunker/recipe/${field}`);
  }
  ctx.ok("units.identity", "ok");
  return true;
}

// U1 ordered unit identity: exactly u0000, u0001, ... (u10000 allowed), with
// unique payload refs. A duplicate/out-of-order ID is caught by the sequence.
function checkUnitIds(ctx, manifest) {
  const seenFiles = new Set();
  for (let i = 0; i < manifest.units.length; i++) {
    const unit = manifest.units[i];
    const expected = `u${String(i).padStart(4, "0")}`;
    if (unit.unit_id !== expected) {
      ctx.stop("units.ids", `unit id/order mismatch: ${i}`);
      return false;
    }
    if (seenFiles.has(unit.file)) {
      ctx.stop("units.ids", `duplicate unit payload: ${q(unit.file)}`);
      return false;
    }
    seenFiles.add(unit.file);
  }
  ctx.ok("units.ids", "ok");
  return true;
}

/** Resolve + read one unit payload; missing bytes are `payload missing`. */
function readPayload(ctx, ref, baseRel, unitId) {
  const resolved = resolveRef(ctx, ref, baseRel);
  if (resolved.bad) {
    ctx.stop("units.payload", `payload missing: ${q(unitId)}`);
    return null;
  }
  if (resolved.escape) {
    ctx.refuse("artifact.path", `artifact path escapes run root: ${resolved.ref}`);
    return null;
  }
  if (resolved.nonregular) {
    ctx.stop("artifact.type", `artifact is not a regular file: ${resolved.ref}`);
    return null;
  }
  if (resolved.missing || resolved.unreadable) {
    ctx.stop("units.payload", `payload missing: ${q(unitId)}`);
    return null;
  }
  const cached = ctx.cache.get(resolved.abs);
  if (cached) return cached;
  try {
    const buf = readFileSync(resolved.abs);
    ctx.cache.set(resolved.abs, buf);
    return buf;
  } catch {
    ctx.stop("units.payload", `payload missing: ${q(unitId)}`);
    return null;
  }
}

// U3 payload existence, pin one-to-one mapping, byte_len and sha256 at the
// OUTDIR-relative location (parent of the units2/ manifest directory). Also
// rejects extra pins and unreferenced uNNNN.txt files; never other files.
function collectUnitPayloads(ctx, manifest, env, unitsRef) {
  const outDirRaw = path.posix.dirname(path.posix.dirname(unitsRef));
  const outDir = outDirRaw === "." ? "" : outDirRaw;

  const pinsByUnit = new Map();
  for (const pin of env.unit_payloads) {
    if (pinsByUnit.has(pin.unit_id)) {
      ctx.stop("units.payload", `duplicate payload pin: ${q(pin.unit_id)}`);
      return null;
    }
    pinsByUnit.set(pin.unit_id, pin);
  }
  const knownIds = new Set(manifest.units.map((u) => u.unit_id));
  for (const pin of env.unit_payloads) {
    if (!knownIds.has(pin.unit_id)) {
      ctx.stop("units.payload", `unassigned payload: ${q(pin.ref)}`);
      return null;
    }
  }

  const payloads = new Map();
  for (const unit of manifest.units) {
    const pin = pinsByUnit.get(unit.unit_id);
    if (!pin) {
      ctx.stop("units.payload", `payload sha256 pin missing: ${q(unit.unit_id)}`);
      return null;
    }
    if (pin.ref !== unit.file) {
      ctx.stop("units.payload", `payload ref mismatch: ${q(unit.unit_id)}`);
      return null;
    }
    if (!isNonEmptyString(pin.sha256)) {
      ctx.stop("units.payload", `payload sha256 pin missing: ${q(unit.unit_id)}`);
      return null;
    }
    const buf = readPayload(ctx, unit.file, outDir, unit.unit_id);
    if (!buf || ctx.aborted) return null;
    if (buf.length !== unit.byte_len) {
      ctx.stop("units.payload", `payload byte_len mismatch: ${q(unit.unit_id)}`);
      return null;
    }
    if (sha256(buf) !== pin.sha256) {
      ctx.stop("units.payload", `payload sha256 mismatch: ${q(unit.unit_id)}`);
      return null;
    }
    payloads.set(unit.unit_id, buf);
  }

  const refs = new Set(manifest.units.map((u) => u.file));
  // Recursive scan of the units root (OUTDIR): any uNNNN.txt not referenced by
  // the manifest/envelope pins is an unassigned payload, in any subdirectory.
  const walkPayloads = (dirRel) => {
    const absDir = dirRel === "." ? path.join(ctx.runRoot, outDir) : path.join(ctx.runRoot, outDir, dirRel);
    let entries;
    try {
      entries = readdirSync(absDir, { withFileTypes: true });
    } catch {
      return true;
    }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const ref = dirRel === "." ? entry.name : `${dirRel}/${entry.name}`;
      if (entry.isDirectory()) {
        if (!walkPayloads(ref)) return false;
        continue;
      }
      if (!(entry.isFile() || entry.isSymbolicLink())) continue;
      if (!PAYLOAD_BASENAME.test(entry.name) || refs.has(ref)) continue;
      const resolved = resolveRef(ctx, ref, outDir);
      if (resolved.escape) {
        ctx.refuse("artifact.path", `artifact path escapes run root: ${resolved.ref}`);
        return false;
      }
      if (resolved.ok) {
        ctx.stop("units.payload", `unassigned payload: ${q(ref)}`);
        return false;
      }
    }
    return true;
  };
  if (!walkPayloads(".")) return null;

  ctx.ok("units.payload", "ok");
  return payloads;
}

// U4 counts recomputed from the units array and actual payload bytes, plus the
// exact changed-file sweep against the capture inventory (no fuzzy matching).
function checkUnitCounts(ctx, manifest, capture, payloads) {
  const recomputed = {
    units: manifest.units.length,
    files: new Set(manifest.units.map((u) => u.path)).size,
    line_split_units: manifest.units.filter((u) => u.boundary_kind === "line-split").length,
    total_bytes: manifest.units.reduce((n, u) => n + payloads.get(u.unit_id).length, 0),
  };
  for (const field of ["units", "files", "line_split_units", "total_bytes"]) {
    if (manifest.counts[field] !== recomputed[field]) {
      ctx.stop("units.counts", `unit count mismatch: ${field}`);
      return false;
    }
  }
  const unitPaths = [...new Set(manifest.units.map((u) => u.path))];
  const changed = new Set(capture.changed_files);
  if (
    capture.changed_files_count !== capture.changed_files.length
    || unitPaths.length !== changed.size
    || unitPaths.some((p) => !changed.has(p))
  ) {
    ctx.stop("units.counts", "changed file sweep mismatch");
    return false;
  }
  ctx.ok(
    "units.counts",
    `units=${recomputed.units} files=${recomputed.files} line_split_units=${recomputed.line_split_units} total_bytes=${recomputed.total_bytes}`,
  );
  return true;
}

// U5 boundary enum + hunk_count/ranges agreement (no unique-line inference).
function checkUnitRanges(ctx, manifest) {
  for (const unit of manifest.units) {
    if (!BOUNDARY_KINDS.has(unit.boundary_kind)) {
      ctx.stop("units.ranges", `invalid boundary_kind: ${q(unit.unit_id)}`);
      return false;
    }
    if (unit.hunk_count !== unit.ranges.length) {
      ctx.stop("units.ranges", `hunk_count mismatch: ${q(unit.unit_id)}`);
      return false;
    }
  }
  ctx.ok("units.ranges", "ok");
  return true;
}

// U6 window ceiling; the only exemption is a genuine no-hunk metadata `file`
// unit (relabelling a hunk payload as `file` is rejected).
function checkUnitBounds(ctx, manifest, payloads) {
  const ceiling = manifest.recipe.ceiling_bytes;
  for (const unit of manifest.units) {
    const buf = payloads.get(unit.unit_id);
    if (unit.boundary_kind === "file") {
      if (!isMetadataOnlyPayload(buf)) {
        ctx.stop("units.bounds", `invalid metadata exemption: ${q(unit.unit_id)}`);
        return false;
      }
    } else if (buf.length > ceiling) {
      ctx.stop("units.bounds", `payload ceiling exceeded: ${q(unit.unit_id)}`);
      return false;
    }
  }
  ctx.ok("units.bounds", "ok");
  return true;
}

// U7 payload diff framing: every line carries a legitimate marker, hunk/content
// fragments must exist for non-metadata units, and a/ b/ paths that are exactly
// representable must match the manifest path. No subject replay.
function checkUnitDiff(ctx, manifest, payloads) {
  for (const unit of manifest.units) {
    const text = decodeUtf8(payloads.get(unit.unit_id));
    if (text === null) {
      ctx.stop("units.diff", `invalid UTF-8: ${q(unit.file)}`);
      return false;
    }
    let hasAnchor = false;
    for (const line of splitPayloadLines(text)) {
      const kind = classifyDiffLine(line);
      if (kind === null) {
        ctx.stop("units.diff", `diff marker missing: ${q(unit.unit_id)}`);
        return false;
      }
      if (kind === "hunk" || kind === "content") hasAnchor = true;
      let pathValue = null;
      if (line.startsWith("diff --git ")) pathValue = gitHeaderPath(line);
      else if (line.startsWith("--- ")) pathValue = signedDiffPath(line, "a");
      else if (line.startsWith("+++ ")) pathValue = signedDiffPath(line, "b");
      if (pathValue !== null && pathValue !== unit.path) {
        ctx.stop("units.diff", `diff path mismatch: ${q(unit.unit_id)}`);
        return false;
      }
    }
    if (unit.boundary_kind !== "file" && !hasAnchor) {
      ctx.stop("units.diff", `diff marker missing: ${q(unit.unit_id)}`);
      return false;
    }
  }
  ctx.ok("units.diff", "ok");
  return true;
}

function runUnits(ctx) {
  const env = loadEnvelope(ctx);
  if (!env || ctx.aborted) return;
  if (!checkVerifier(ctx, env)) return;
  declaredSchema(ctx, env.units_manifest, "/units_manifest", "units");
  if (ctx.aborted) return;
  const ref = discoverPrimary(ctx, "units", env);
  if (!ref || ctx.aborted) return;
  const primary = loadPrimary(ctx, "units", ref);
  if (!primary || ctx.aborted) return;
  const manifest = primary.obj;

  if (!checkUnitsEnvelopeShape(ctx, env) || ctx.aborted) return;
  const captureLoad = loadCapture(ctx, env);
  if (!captureLoad || ctx.aborted) return;
  const capture = captureLoad.capture;
  ctx.capture = capture;
  if (!Array.isArray(capture.changed_files)) {
    ctx.stop("shape", "invalid field: /changed_files expected array");
    return;
  }
  if (!isNonNegInt(capture.changed_files_count)) {
    ctx.stop("shape", "invalid field: /changed_files_count expected nonnegative integer");
    return;
  }

  const shapeFailure = validateUnitsShape(manifest);
  if (shapeFailure) {
    ctx.stop("shape", shapeFailure);
    return;
  }
  ctx.ok("shape", "ok");

  checkUnitsIdentity(ctx, env, manifest, capture);
  if (!checkUnitIds(ctx, manifest) || ctx.aborted) return;
  const payloads = collectUnitPayloads(ctx, manifest, env, ref);
  if (!payloads || ctx.aborted) return;
  ctx.payloads = payloads;
  if (!checkUnitCounts(ctx, manifest, capture, payloads) || ctx.aborted) return;
  if (!checkUnitRanges(ctx, manifest) || ctx.aborted) return;
  if (!checkUnitBounds(ctx, manifest, payloads) || ctx.aborted) return;
  checkUnitDiff(ctx, manifest, payloads);
}

// ---------------------------------------------------------------------------
// join — join-draft/1 (J1..J7 implemented in P4a; J8..J12 explicit stubs)
// ---------------------------------------------------------------------------

const CLOSENESS_VALUES = new Set(["high", "medium", "low"]);
const ROLE_VALUES = new Set(["implements", "tests", "necessary-support", "removes", "changes"]);

/**
 * Witness marker rule (plan §2/§3 J6): the witness must start a payload line
 * whose first character is `+`, `-`, a space context, or `@@ `; `file` metadata
 * units additionally accept the frozen METADATA_PREFIXES list. Mid-line plus
 * signs never count and `\ No newline` lines are not markers.
 */
function witnessMarkerAllowed(unit, text) {
  const head = text[0];
  if (head === "+" || head === "-" || head === " ") return true;
  if (text.startsWith("@@ ")) return true;
  return unit.boundary_kind === "file" && classifyDiffLine(text) === "metadata";
}

/** First byte offset where `needle` starts at a payload line boundary, or -1. */
function findAtLineBoundary(payload, needle) {
  for (let i = payload.indexOf(needle); i !== -1; i = payload.indexOf(needle, i + 1)) {
    if (i === 0 || payload[i - 1] === 0x0a) return i;
  }
  return -1;
}

/**
 * Run one prerequisite command (claims/units) in an isolated collector that
 * shares the byte cache. Any failure there is fatal for join (P3 open question
 * 2): a join verdict may never be produced over invalid prerequisites.
 */
function runPrerequisite(ctx, command) {
  const sub = new Ctx(ctx.runRoot);
  sub.cache = ctx.cache;
  if (command === "claims") runClaims(sub);
  else runUnits(sub);
  return sub;
}

/**
 * A prerequisite refusal (unknown/wrong-kind schema, exit 2) keeps code 2 and
 * names the unsupported schema; ordinary prerequisite failures stay code 1.
 */
function failPrerequisite(ctx, command, sub) {
  const refused = sub.checks.find((check) => !check.ok && check.code === 2);
  if (refused) return ctx.refuse("join.prerequisites", `prerequisite refused: ${command}: ${refused.detail}`);
  return ctx.stop("join.prerequisites", `prerequisite failed: ${command}`);
}

/**
 * Dispatch for an optional schema_version on join support artifacts. Support
 * records (assignment, claims-list, p05-check, p05-evidence) are unversioned
 * contract artifacts (F15): an unknown schema refuses 2, and ANY registered
 * schema is a wrong-kind refusal 2; absent => the legacy parser is unchanged.
 */
function dispatchSupportSchema(ctx, obj, pointer) {
  if (!isPlainObject(obj) || obj.schema_version === undefined) return true;
  const sv = obj.schema_version;
  if (!isNonEmptyString(sv)) {
    ctx.stop("schema", `invalid field: ${pointer}/schema_version expected nonempty string`);
    return false;
  }
  if (!REGISTRY.get(sv)) {
    ctx.refuse("schema", `unsupported schema_version: ${q(sv)}`);
    return false;
  }
  ctx.refuse("artifact.discovery", `wrong schema kind: ${q(sv)} for join`);
  return false;
}

/**
 * Support artifacts are parsed and top-level shape-checked before row checks
 * (instruction markdown carries no JSON): assignment and both p05 records must
 * be non-null objects, the claims-list payload must be an array, and an
 * object-form claims-list carrying schema_version is dispatched (and always
 * refused) before the array shape check (F14/F15).
 */
function checkSupportSchemas(ctx, env) {
  for (let i = 0; i < env.join_boxes.length; i++) {
    const entry = env.join_boxes[i];
    for (const key of ["assignment", "claims_list", "p05_check", "p05_evidence"]) {
      const ref = entry[key].ref;
      const buf = readArtifact(ctx, ref);
      if (!buf || ctx.aborted) return false;
      const pointer = `/join_boxes/${i}/${key}`;
      if (key === "claims_list") {
        const list = parseJsonArtifact(ctx, ref, buf);
        if (ctx.aborted) return false;
        if (isPlainObject(list) && list.schema_version !== undefined) {
          if (!dispatchSupportSchema(ctx, list, pointer)) return false;
        } else if (!Array.isArray(list)) {
          return ctx.stop("shape", "invalid field: / expected array");
        }
      } else {
        const obj = parseJsonObjectArtifact(ctx, ref, buf);
        if (!obj || ctx.aborted) return false;
        if (!dispatchSupportSchema(ctx, obj, pointer)) return false;
      }
    }
  }
  return true;
}

/** Envelope join-box/attempt slices must be present and array-typed. */
function checkJoinEnvelopeBoxes(ctx, env) {
  if (!Array.isArray(env.join_boxes)) return ctx.stop("shape", "invalid field: /join_boxes expected array");
  if (env.join_attempts !== undefined && !Array.isArray(env.join_attempts)) {
    return ctx.stop("shape", "invalid field: /join_attempts expected array");
  }
  return true;
}

/** Read+pin every boxed input (assignment/instructions/claims_list/p05) and attempt output. */
function pinJoinSupportArtifacts(ctx, env) {
  for (let i = 0; i < env.join_boxes.length; i++) {
    const entry = env.join_boxes[i];
    if (!isPlainObject(entry)) return ctx.stop("shape", `invalid field: /join_boxes/${i} expected object`);
    if (!isNonEmptyString(entry.box_id)) return ctx.stop("shape", `invalid field: /join_boxes/${i}/box_id expected nonempty string`);
    for (const key of ["assignment", "instructions", "claims_list", "p05_check", "p05_evidence"]) {
      const pin = entry[key];
      if (!isPlainObject(pin)) return ctx.stop("shape", `invalid field: /join_boxes/${i}/${key} expected object`);
      if (!isNonEmptyString(pin.ref)) return ctx.stop("shape", `invalid field: /join_boxes/${i}/${key}/ref expected nonempty string`);
      const buf = readArtifact(ctx, pin.ref);
      if (!buf || ctx.aborted) return false;
      checkPin(ctx, pin.ref, buf, pin.sha256);
    }
  }
  if (Array.isArray(env.join_attempts)) {
    for (let i = 0; i < env.join_attempts.length; i++) {
      const attempt = env.join_attempts[i];
      if (!isPlainObject(attempt)) return ctx.stop("shape", `invalid field: /join_attempts/${i} expected object`);
      if (!isNonEmptyString(attempt.attempt_id)) return ctx.stop("shape", `invalid field: /join_attempts/${i}/attempt_id expected nonempty string`);
      if (!isPlainObject(attempt.output) || !isNonEmptyString(attempt.output.ref)) {
        return ctx.stop("shape", `invalid field: /join_attempts/${i}/output/ref expected nonempty string`);
      }
      const buf = readArtifact(ctx, attempt.output.ref);
      if (!buf || ctx.aborted) return false;
      checkPin(ctx, attempt.output.ref, buf, attempt.output.sha256);
    }
  }
  return true;
}

/** J1: join-draft identity + units_manifest binding (box pins validated separately). */
function checkJoinBinding(ctx, join, unitsRef, unitsBuf, unitsObj) {
  if (!isPlainObject(join.units_manifest)) return ctx.stop("shape", "invalid field: /units_manifest expected object");
  const um = join.units_manifest;
  const bad = () => {
    ctx.fail("join.identity", "join manifest binding mismatch");
    ctx.aborted = true;
    return false;
  };
  if (um.ref !== unitsRef) return bad();
  if (um.sha256 !== sha256(unitsBuf)) return bad();
  if (um.schema_version !== "code-units-sim/2") return bad();
  if (um.unit_count !== unitsObj.units.length) return bad();
  if (!Array.isArray(join.boxes)) return ctx.stop("shape", "invalid field: /boxes expected array");
  for (let i = 0; i < join.boxes.length; i++) {
    const box = join.boxes[i];
    if (!isPlainObject(box)) return ctx.stop("shape", `invalid field: /boxes/${i} expected object`);
    if (!isNonEmptyString(box.box_id)) return ctx.stop("shape", `invalid field: /boxes/${i}/box_id expected nonempty string`);
    if (!isNonEmptyString(box.path)) return ctx.stop("shape", `invalid field: /boxes/${i}/path expected nonempty string`);
    if (!isNonEmptyString(box.sha256)) return ctx.stop("shape", `invalid field: /boxes/${i}/sha256 expected nonempty string`);
    if (!isNonNegInt(box.rows)) return ctx.stop("shape", `invalid field: /boxes/${i}/rows expected nonnegative integer`);
    if (!isNonNegInt(box.links)) return ctx.stop("shape", `invalid field: /boxes/${i}/links expected nonnegative integer`);
  }
  ctx.ok("join.identity", "ok");
  return true;
}

/** J2: envelope/join boxes bijection, assignment binding, per-box and global sweeps. */
function checkJoinAssignments(ctx, env, join, unitsObj, unitsRef, unitsBuf) {
  const manifestIds = unitsObj.units.map((u) => u.unit_id);
  const manifestIndex = new Map(manifestIds.map((id, k) => [id, k]));
  const fail = (detail) => {
    ctx.fail("join.assignments", detail);
    return null;
  };
  if (env.join_boxes.length !== join.boxes.length) {
    return fail(`box assignment binding mismatch: ${q(join.boxes[0]?.box_id ?? env.join_boxes[0]?.box_id ?? "?")}`);
  }
  const assignments = new Map();
  for (let i = 0; i < join.boxes.length; i++) {
    const box = join.boxes[i];
    const entry = env.join_boxes[i];
    if (!isPlainObject(entry) || entry.box_id !== box.box_id || !isPlainObject(entry.assignment)) {
      return fail(`box assignment binding mismatch: ${q(box.box_id)}`);
    }
    const assignmentBuf = readArtifact(ctx, entry.assignment.ref);
    if (!assignmentBuf || ctx.aborted) return null;
    const assignment = parseJsonObjectArtifact(ctx, entry.assignment.ref, assignmentBuf);
    if (!assignment || ctx.aborted) return null;
    if (assignment.box_id !== box.box_id || assignment.output_path !== box.path) {
      return fail(`box assignment binding mismatch: ${q(box.box_id)}`);
    }
    if (
      assignment.units_dir !== path.posix.dirname(unitsRef)
      || assignment.manifest_ref !== unitsRef
      || assignment.manifest_sha256 !== sha256(unitsBuf)
      || assignment.claims_list_path !== entry.claims_list.ref
    ) {
      return fail(`box assignment binding mismatch: ${q(box.box_id)}`);
    }
    if (!Array.isArray(assignment.units)) return fail(`box assignment binding mismatch: ${q(box.box_id)}`);
    if (assignment.unit_count !== assignment.units.length) {
      return fail(`assignment unit count mismatch: ${q(box.box_id)}`);
    }
    const seen = new Set();
    let last = -1;
    for (const id of assignment.units) {
      if (!manifestIndex.has(id)) return fail(`assigned unit not found: ${q(id)}`);
      if (seen.has(id)) return fail(`assigned unit duplicate: ${q(id)}`);
      seen.add(id);
      const idx = manifestIndex.get(id);
      if (idx <= last) return fail("assigned unit sweep mismatch");
      last = idx;
    }
    assignments.set(box.box_id, assignment);
  }
  const sweep = [];
  for (const box of join.boxes) sweep.push(...assignments.get(box.box_id).units);
  if (sweep.length !== manifestIds.length || sweep.some((id, k) => id !== manifestIds[k])) {
    return fail("assigned unit sweep mismatch");
  }
  ctx.ok("join.assignments", "ok");
  return assignments;
}

/** J3: strict row/link shapes and enums. */
function validateJoinRows(ctx, boxes) {
  const bad = (detail) => {
    ctx.fail("join.rows", detail);
    return false;
  };
  for (const { box, rows } of boxes) {
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const p = `/rows/${box.box_id}/${i}`;
      if (!isPlainObject(row)) return bad(`invalid field: ${p} expected object`);
      for (const key of Object.keys(row)) {
        if (key !== "unit_id" && key !== "links" && key !== "unresolved") return bad(`unexpected field: ${p}/${key}`);
      }
      if (!isNonEmptyString(row.unit_id)) return bad(`invalid field: ${p}/unit_id expected nonempty string`);
      if (!Array.isArray(row.links)) return bad(`invalid field: ${p}/links expected array`);
      if (row.unresolved !== null && !isNonEmptyString(row.unresolved)) {
        return bad(`invalid field: ${p}/unresolved expected null or nonempty string`);
      }
      for (let j = 0; j < row.links.length; j++) {
        const link = row.links[j];
        const lp = `${p}/links/${j}`;
        if (!isPlainObject(link)) return bad(`invalid field: ${lp} expected object`);
        for (const key of Object.keys(link)) {
          if (key !== "claim_id" && key !== "closeness" && key !== "role_hint" && key !== "witness") {
            return bad(`unexpected field: ${lp}/${key}`);
          }
        }
        if (!isNonEmptyString(link.claim_id)) return bad(`invalid field: ${lp}/claim_id expected nonempty string`);
        if (typeof link.closeness !== "string") return bad(`invalid field: ${lp}/closeness expected string`);
        if (!CLOSENESS_VALUES.has(link.closeness)) return bad(`invalid closeness: ${q(box.box_id)}:${q(row.unit_id)}:${q(link.closeness)}`);
        if (typeof link.role_hint !== "string") return bad(`invalid field: ${lp}/role_hint expected string`);
        if (!ROLE_VALUES.has(link.role_hint)) return bad(`invalid role_hint: ${q(box.box_id)}:${q(row.unit_id)}:${q(link.role_hint)}`);
        if (typeof link.witness !== "string") return bad(`invalid field: ${lp}/witness expected string`);
      }
    }
  }
  ctx.ok("join.rows", "ok");
  return true;
}

/** J4: parsed rows must project the assignment unit list exactly, in order. */
function checkJoinOrder(ctx, boxes, assignments) {
  for (const { box, rows } of boxes) {
    const actual = rows.map((r) => r.unit_id);
    const expected = assignments.get(box.box_id).units;
    if (actual.length !== expected.length || actual.some((id, k) => id !== expected[k])) {
      ctx.fail("join.order", `box unit sweep/order mismatch: ${q(box.box_id)}`);
      return false;
    }
  }
  ctx.ok("join.order", "ok");
  return true;
}

/** J5: claim ids resolve against the full claims draft; (unit,claim) pairs unique. */
function checkJoinPairs(ctx, claims, boxes) {
  const claimIds = new Set(claims.claims.map((c) => c.id));
  const pairs = new Set();
  for (const { rows } of boxes) {
    for (const row of rows) {
      for (const link of row.links) {
        if (!claimIds.has(link.claim_id)) {
          ctx.fail("join.pairs", `join claim id not found: ${q(row.unit_id)} -> ${q(link.claim_id)}`);
          return false;
        }
        const key = `${row.unit_id}\u0000${link.claim_id}`;
        if (pairs.has(key)) {
          ctx.fail("join.pairs", `duplicate unit/claim pair: ${q(row.unit_id)} -> ${q(link.claim_id)}`);
          return false;
        }
        pairs.add(key);
      }
    }
  }
  ctx.ok("join.pairs", "ok");
  return true;
}

/** J6: witness nonempty/single-line/<=160 codepoints/byte substring/line-start marker. */
function checkJoinWitness(ctx, unitsObj, payloads, boxes) {
  const unitsById = new Map(unitsObj.units.map((u) => [u.unit_id, u]));
  for (const { rows } of boxes) {
    for (const row of rows) {
      const unit = unitsById.get(row.unit_id);
      const payload = payloads.get(row.unit_id);
      for (const link of row.links) {
        const witness = link.witness;
        const where = `${q(row.unit_id)} -> ${q(link.claim_id)}`;
        if (witness.length === 0) {
          ctx.fail("join.witness", `empty witness: ${where}`);
          return false;
        }
        if (witness.includes("\n") || witness.includes("\r")) {
          ctx.fail("join.witness", `multiline witness: ${where}`);
          return false;
        }
        if (Array.from(witness).length > 160) {
          ctx.fail("join.witness", `witness exceeds 160 characters: ${where}`);
          return false;
        }
        const needle = Buffer.from(witness, "utf8");
        const atBoundary = payload ? findAtLineBoundary(payload, needle) : -1;
        if (atBoundary === -1) {
          if (payload && payload.includes(needle)) ctx.fail("join.witness", `witness diff marker missing: ${where}`);
          else ctx.fail("join.witness", `witness not in unit: ${where}`);
          return false;
        }
        if (!witnessMarkerAllowed(unit, witness)) {
          ctx.fail("join.witness", `witness diff marker missing: ${where}`);
          return false;
        }
      }
    }
  }
  ctx.ok("join.witness", "ok");
  return true;
}

/** J7: claims-list is the exact ordered {id,statement} projection + recorded byte length. */
function checkJoinClaimList(ctx, env, join, assignments, claims) {
  const projection = claims.claims.map((c) => ({ id: c.id, statement: c.statement }));
  for (let i = 0; i < join.boxes.length; i++) {
    const box = join.boxes[i];
    const entry = env.join_boxes[i];
    const buf = readArtifact(ctx, entry.claims_list.ref);
    if (!buf || ctx.aborted) return false;
    const list = parseJsonArrayArtifact(ctx, entry.claims_list.ref, buf);
    if (!list || ctx.aborted) return false;
    let same = list.length === projection.length;
    if (same) {
      for (let j = 0; j < projection.length; j++) {
        const item = list[j];
        if (
          !isPlainObject(item)
          || Object.keys(item).length !== 2
          || item.id !== projection[j].id
          || item.statement !== projection[j].statement
        ) {
          same = false;
          break;
        }
      }
    }
    if (!same) {
      ctx.fail("join.claim_list", `claims list mismatch: ${q(box.box_id)}`);
      return false;
    }
    if (assignments.get(box.box_id).claims_list_bytes !== buf.length) {
      ctx.fail("join.claim_list", `claims_list_bytes mismatch: ${q(box.box_id)}`);
      return false;
    }
  }
  ctx.ok("join.claim_list", "ok");
  return true;
}

/**
 * J8: recompute input/output budget metrics (plan §3 J8). Unit bytes come from
 * the assigned payload buffers, instructions bytes from the exact .md,
 * claims-list bytes from the exact list; total = fixed + units. The recorded
 * assignment/p05 metrics must equal the recomputed values, both recorded
 * ceilings must equal the independent approved pilot ceiling, and the
 * recomputed input must fit it. Output bytes are always measured against the
 * accepted box file; a numeric pilot output ceiling is enforced, null/absent
 * yields the monitoring-only pass detail. Accepted non-recovery boxes must be
 * greedily packed (recovery halves exempt).
 */
function checkJoinBudget(ctx, env, boxes, assignments, payloads) {
  const pilot = isPlainObject(env.pilot) ? env.pilot : null;
  if (!pilot || !isNonNegInt(pilot.input_ceiling_bytes)) {
    ctx.fail("join.budget", "pilot input ceiling missing");
    return false;
  }
  if (pilot.witness_max_chars !== 160) {
    ctx.fail("join.budget", "pilot witness_max_chars mismatch");
    return false;
  }
  const approved = pilot.input_ceiling_bytes;
  const recovery = new Set();
  if (Array.isArray(env.join_attempts)) {
    for (const attempt of env.join_attempts) {
      if (
        isPlainObject(attempt)
        && isNonEmptyString(attempt.box_id)
        && attempt.parent_box_id !== null
        && attempt.parent_box_id !== undefined
      ) {
        recovery.add(attempt.box_id);
      }
    }
  }
  const fail = (detail) => {
    ctx.fail("join.budget", detail);
    return false;
  };
  const inputs = [];
  let totalOutputBytes = 0;
  for (const { box, rows, buf } of boxes) {
    const assignment = assignments.get(box.box_id);
    const entry = env.join_boxes.find((candidate) => isPlainObject(candidate) && candidate.box_id === box.box_id);
    if (!entry) return fail(`pilot ceiling mismatch: ${q(box.box_id)}`);
    const unitBytes = assignment.units.reduce((n, id) => n + payloads.get(id).length, 0);
    const instructionsBuf = readArtifact(ctx, entry.instructions.ref);
    const claimsListBuf = readArtifact(ctx, entry.claims_list.ref);
    if (!instructionsBuf || !claimsListBuf || ctx.aborted) return false;
    const p05Buf = readArtifact(ctx, entry.p05_evidence.ref);
    if (!p05Buf || ctx.aborted) return false;
    const p05 = parseJsonObjectArtifact(ctx, entry.p05_evidence.ref, p05Buf);
    if (!p05 || ctx.aborted) return false;
    const budget = isPlainObject(p05.budget) ? p05.budget : {};
    const boxInput = unitBytes + claimsListBuf.length + instructionsBuf.length;
    if (assignment.input_ceiling_bytes !== approved || budget.input_ceiling_bytes !== approved) {
      return fail(`pilot ceiling mismatch: ${q(box.box_id)}`);
    }
    if (boxInput > approved) return fail(`input budget exceeded: ${q(box.box_id)}`);
    if (assignment.total_unit_bytes !== unitBytes) return fail(`budget metric mismatch: ${q(box.box_id)}:total_unit_bytes`);
    if (budget.unit_bytes !== unitBytes) return fail(`budget metric mismatch: ${q(box.box_id)}:unit_bytes`);
    if (budget.claims_list_bytes !== claimsListBuf.length) return fail(`budget metric mismatch: ${q(box.box_id)}:claims_list_bytes`);
    if (budget.instructions_bytes !== instructionsBuf.length) return fail(`budget metric mismatch: ${q(box.box_id)}:instructions_bytes`);
    if (budget.box_input_bytes !== boxInput) return fail(`budget metric mismatch: ${q(box.box_id)}:box_input_bytes`);
    if (budget.headroom_bytes !== approved - boxInput) return fail(`budget metric mismatch: ${q(box.box_id)}:headroom_bytes`);
    const outputBytes = buf.length;
    const links = rows.reduce((n, row) => n + row.links.length, 0);
    if (budget.output_bytes !== outputBytes) return fail(`budget metric mismatch: ${q(box.box_id)}:output_bytes`);
    if (budget.output_links !== links) return fail(`budget metric mismatch: ${q(box.box_id)}:output_links`);
    if (typeof pilot.output_ceiling_bytes === "number" && outputBytes > pilot.output_ceiling_bytes) {
      return fail(`output budget exceeded: ${q(box.box_id)}`);
    }
    inputs.push(boxInput);
    totalOutputBytes += outputBytes;
  }
  for (let i = 0; i + 1 < boxes.length; i++) {
    const boxId = boxes[i].box.box_id;
    if (recovery.has(boxId)) continue;
    const nextUnit = assignments.get(boxes[i + 1].box.box_id).units[0];
    if (!nextUnit) continue;
    if (payloads.get(nextUnit).length <= approved - inputs[i]) {
      return fail(`non-greedy box packing: ${q(boxId)}`);
    }
  }
  if (typeof pilot.output_ceiling_bytes === "number") {
    ctx.ok("join.budget", `output_bytes=${totalOutputBytes}; output ceiling=${pilot.output_ceiling_bytes}`);
  } else {
    ctx.ok("join.budget", `output_bytes=${totalOutputBytes}; output ceiling not declared (monitoring only)`);
  }
  return true;
}

/**
 * J9: structured retry/resplit history (plan §3 J9). Only recorded accepted
 * leaves form the current sweep; attempt 1 may be retried once with the same
 * assignment, and only after both attempts fail may a box split into two
 * ordered halves (`resplit:'halves'`: left = floor(n/2) units, right = the
 * remainder so the right half is larger for odd n), both nonempty, manifest
 * order preserved, no unit split, depth ≤ pilot.max_resplit_depth. A singleton
 * can never split. Exact floor geometry is mechanically enforced.
 */
function checkJoinRecovery(ctx, env, join, assignments) {
  const fail = (detail) => {
    ctx.fail("join.recovery", detail);
    return false;
  };
  const attempts = Array.isArray(env.join_attempts) ? env.join_attempts : [];
  for (const a of attempts) {
    if (
      !isPlainObject(a)
      || !isNonEmptyString(a.attempt_id)
      || !isNonEmptyString(a.box_id)
      || (a.parent_box_id !== null && a.parent_box_id !== undefined && !isNonEmptyString(a.parent_box_id))
      || !isNonNegInt(a.attempt)
      || a.attempt < 1
      || !Array.isArray(a.units)
      || a.units.some((id) => !isNonEmptyString(id))
      || (a.status !== "failed" && a.status !== "accepted")
    ) {
      return fail("retry policy mismatch");
    }
  }
  const pilot = isPlainObject(env.pilot) ? env.pilot : null;
  if (!pilot || pilot.retry_limit !== 1 || pilot.resplit !== "halves" || pilot.max_resplit_depth !== 1) {
    return fail("retry policy mismatch");
  }
  const groups = new Map();
  for (const a of attempts) {
    if (!groups.has(a.box_id)) groups.set(a.box_id, []);
    groups.get(a.box_id).push(a);
  }
  const parentsOf = new Map();
  const childOrder = new Map();
  for (const a of attempts) {
    if (a.parent_box_id === null || a.parent_box_id === undefined) continue;
    if (parentsOf.has(a.box_id)) {
      if (parentsOf.get(a.box_id) !== a.parent_box_id) return fail("retry policy mismatch");
      continue;
    }
    parentsOf.set(a.box_id, a.parent_box_id);
    if (!childOrder.has(a.parent_box_id)) childOrder.set(a.parent_box_id, []);
    childOrder.get(a.parent_box_id).push(a.box_id);
  }
  const depthOf = (boxId) => {
    let depth = 0;
    let cursor = boxId;
    const seen = new Set();
    while (parentsOf.has(cursor)) {
      if (seen.has(cursor)) break;
      seen.add(cursor);
      cursor = parentsOf.get(cursor);
      depth += 1;
    }
    return depth;
  };
  // A superseded accepted parent must never stay in the current sweep.
  for (const a of attempts) {
    if (a.status === "accepted" && childOrder.has(a.box_id)) {
      return fail(`stale accepted attempt: ${q(a.box_id)}`);
    }
  }
  // Split policy and exact halves geometry for every recorded parent box.
  for (const [parentId, children] of childOrder) {
    const group = groups.get(parentId) ?? [];
    const parentUnits = group.length > 0 ? group[0].units : [];
    if (parentUnits.length < 2) return fail(`resplit halves mismatch: ${q(parentId)}`);
    if (group.length !== 2 || group[0].status !== "failed" || group[1].status !== "failed") {
      return fail("retry policy mismatch");
    }
    const childUnits = children.map((childId) => (groups.get(childId) ?? [])[0]?.units ?? null);
    const childLeft = childUnits[0] ?? [];
    const childRight = childUnits[1] ?? [];
    const leftLength = Math.floor(parentUnits.length / 2);
    const halvesMatch =
      children.length === 2
      && childLeft.length === leftLength
      && childRight.length === parentUnits.length - leftLength
      && sameArray([...childLeft, ...childRight], parentUnits);
    if (!halvesMatch) return fail(`resplit halves mismatch: ${q(parentId)}`);
    if (depthOf(parentId) >= pilot.max_resplit_depth) return fail(`resplit depth exceeded: ${q(parentId)}`);
  }
  // Per-box attempt policy: numbering, one retry, same assignment, accepted last.
  for (const [boxId, group] of groups) {
    if (group.length > pilot.retry_limit + 1) return fail(`retry limit exceeded: ${q(boxId)}`);
    for (let i = 0; i < group.length; i++) {
      if (group[i].attempt !== i + 1) return fail("retry policy mismatch");
      if (i > 0 && !sameArray(group[i].units, group[0].units)) return fail("retry policy mismatch");
      if (i < group.length - 1 && group[i].status === "accepted") return fail(`stale accepted attempt: ${q(boxId)}`);
    }
  }
  const currentIds = new Set(join.boxes.map((box) => box.box_id));
  const boxById = new Map(join.boxes.map((box) => [box.box_id, box]));
  for (const a of attempts) {
    if (a.status !== "accepted") continue;
    if (!currentIds.has(a.box_id)) return fail(`stale accepted attempt: ${q(a.box_id)}`);
    const acceptedUnits = assignments.get(a.box_id)?.units;
    if (!acceptedUnits || !sameArray(a.units, acceptedUnits)) return fail("retry policy mismatch");
    // The accepted attempt output must be the current box artifact for that box.
    const currentBox = boxById.get(a.box_id);
    if (a.output.ref !== currentBox.path || a.output.sha256 !== currentBox.sha256) {
      return fail(`stale accepted attempt: ${q(a.box_id)}`);
    }
  }
  for (const box of join.boxes) {
    if (!attempts.some((a) => a.box_id === box.box_id && a.status === "accepted")) {
      return fail(`retry evidence missing: ${q(box.box_id)}`);
    }
  }
  ctx.ok("join.recovery", "ok");
  return true;
}

/**
 * J10: canonical ordered merge equality with the current box rows (object key
 * order ignored, array order preserved) plus declared per-box row/link counts
 * recomputed from the exact box files. The merge is prepared but never trusted
 * over the boxes it is merged from.
 */
function checkJoinMerge(ctx, join, boxes) {
  const fail = (detail) => {
    ctx.fail("join.merge", detail);
    return false;
  };
  const merged = [];
  for (const { rows } of boxes) merged.push(...rows);
  if (!Array.isArray(join.units) || JSON.stringify(canonicalJson(join.units)) !== JSON.stringify(canonicalJson(merged))) {
    return fail("merged join differs from boxes");
  }
  for (const { box, rows } of boxes) {
    let links = 0;
    for (const row of rows) links += row.links.length;
    if (box.rows !== rows.length) return fail(`box count mismatch: ${q(box.box_id)}:rows`);
    if (box.links !== links) return fail(`box count mismatch: ${q(box.box_id)}:links`);
  }
  ctx.ok("join.merge", "ok");
  return true;
}

/**
 * J11: recompute p05 coordinator evidence from the parsed rows and the full
 * claim set — row/link counts, errors, duplicate pairs, zero-link units and
 * claims, unresolved rows and per-claim link counts. Prose fields
 * (witness_containment, retry_history) are never trusted.
 */
function checkJoinP05(ctx, env, boxes, claims) {
  const fail = (detail) => {
    ctx.fail("join.p05", detail);
    return false;
  };
  const claimIds = claims.claims.map((claim) => claim.id);
  for (const { box, rows } of boxes) {
    const entry = env.join_boxes.find((candidate) => isPlainObject(candidate) && candidate.box_id === box.box_id);
    const checkBuf = readArtifact(ctx, entry.p05_check.ref);
    const evidenceBuf = readArtifact(ctx, entry.p05_evidence.ref);
    if (!checkBuf || !evidenceBuf || ctx.aborted) return false;
    const check = parseJsonObjectArtifact(ctx, entry.p05_check.ref, checkBuf);
    const evidence = parseJsonObjectArtifact(ctx, entry.p05_evidence.ref, evidenceBuf);
    if (!check || !evidence || ctx.aborted) return false;
    const rowCount = rows.length;
    const links = rows.reduce((n, row) => n + row.links.length, 0);
    const counts = new Map(claimIds.map((id) => [id, 0]));
    const seen = new Set();
    let duplicatePairs = 0;
    for (const row of rows) {
      for (const link of row.links) {
        counts.set(link.claim_id, (counts.get(link.claim_id) ?? 0) + 1);
        const key = `${row.unit_id}\u0000${link.claim_id}`;
        if (seen.has(key)) duplicatePairs += 1;
        else seen.add(key);
      }
    }
    const zeroUnits = rows.filter((row) => row.links.length === 0).map((row) => row.unit_id);
    const zeroClaims = claimIds.filter((id) => (counts.get(id) ?? 0) === 0);
    const unresolved = rows.filter((row) => row.unresolved !== null).map((row) => row.unit_id);
    for (const [source, field, value] of [
      [evidence, "expected_rows", rowCount],
      [evidence, "received_rows", rowCount],
      [check, "expected_rows", rowCount],
      [check, "file_rows", rowCount],
      [evidence, "total_links", links],
      [check, "total_links", links],
    ]) {
      if (source[field] !== value) return fail(`p05 count mismatch: ${q(box.box_id)}:${field}`);
    }
    if (
      evidence.error_count !== 0 || !Array.isArray(evidence.errors) || evidence.errors.length !== 0
      || check.error_count !== 0 || !Array.isArray(check.errors) || check.errors.length !== 0
    ) {
      return fail(`p05 errors recorded: ${q(box.box_id)}`);
    }
    if (evidence.duplicate_pairs !== 0 || duplicatePairs !== 0) {
      return fail(`p05 count mismatch: ${q(box.box_id)}:duplicate_pairs`);
    }
    for (const [source, field, value] of [
      [evidence, "zero_units", zeroUnits],
      [check, "zero_units", zeroUnits],
      [evidence, "zero_claims", zeroClaims],
      [check, "zero_claims", zeroClaims],
      [evidence, "unresolved", unresolved],
      [check, "unresolved", unresolved],
    ]) {
      if (!sameArray(source[field], value)) return fail(`p05 zero/unresolved mismatch: ${q(box.box_id)}:${field}`);
    }
    const expectedCounts = Object.fromEntries(claimIds.map((id) => [id, counts.get(id)]));
    if (JSON.stringify(canonicalJson(check.claim_link_counts)) !== JSON.stringify(canonicalJson(expectedCounts))) {
      return fail(`p05 claim_link_counts mismatch: ${q(box.box_id)}`);
    }
  }
  ctx.ok("join.p05", "ok");
  return true;
}

/**
 * J12: candidate_unclaimed is the exact manifest-ordered set of zero-link
 * decidable units; every entry must be a known unit whose row has links=[] and
 * unresolved === null. A non-null unresolved row is never decidable; no
 * semantic UNCLAIMED inference is made.
 */
function checkJoinCandidates(ctx, join, boxes, unitsObj) {
  const fail = (detail) => {
    ctx.fail("join.candidates", detail);
    return false;
  };
  const candidate = join.candidate_unclaimed;
  if (!Array.isArray(candidate)) return fail("invalid field: /candidate_unclaimed expected array");
  const known = new Set(unitsObj.units.map((unit) => unit.unit_id));
  const rowById = new Map();
  for (const { rows } of boxes) for (const row of rows) rowById.set(row.unit_id, row);
  const seen = new Set();
  for (const id of candidate) {
    const row = isNonEmptyString(id) ? rowById.get(id) : undefined;
    if (!isNonEmptyString(id) || !known.has(id) || seen.has(id) || !row || row.links.length !== 0 || row.unresolved !== null) {
      return fail(`invalid candidate_unclaimed unit: ${q(id)}`);
    }
    seen.add(id);
  }
  const expected = [];
  for (const { rows } of boxes) {
    for (const row of rows) {
      if (row.links.length === 0 && row.unresolved === null) expected.push(row.unit_id);
    }
  }
  if (!sameArray(candidate, expected)) return fail("candidate_unclaimed set mismatch");
  ctx.ok("join.candidates", "ok");
  return true;
}

function runJoin(ctx) {
  const env = loadEnvelope(ctx);
  if (!env || ctx.aborted) return;
  if (!checkVerifier(ctx, env)) return;
  declaredSchema(ctx, env.join_draft, "/join_draft", "join");
  if (ctx.aborted) return;
  if (!checkJoinEnvelopeBoxes(ctx, env)) return;
  const ref = discoverPrimary(ctx, "join", env);
  if (!ref || ctx.aborted) return;
  const primary = loadPrimary(ctx, "join", ref);
  if (!primary || ctx.aborted) return;
  const join = primary.obj;

  // Prerequisites: claims + units must validate fully; failure is fatal.
  // Unknown/wrong-kind prerequisite schemas keep their exit-2 refusal.
  const claimsCtx = runPrerequisite(ctx, "claims");
  if (claimsCtx.checks.some((c) => !c.ok) || claimsCtx.aborted) return failPrerequisite(ctx, "claims", claimsCtx);
  const unitsCtx = runPrerequisite(ctx, "units");
  if (unitsCtx.checks.some((c) => !c.ok) || unitsCtx.aborted) return failPrerequisite(ctx, "units", unitsCtx);
  const claims = claimsCtx.primary.obj;
  const units = unitsCtx.primary.obj;
  const unitsRef = unitsCtx.primary.ref;
  const unitsBuf = unitsCtx.primary.buf;
  const capture = claimsCtx.capture;

  // J1 identity + binding, then every boxed artifact pin BEFORE row parsing.
  const identityBefore = ctx.checks.length;
  checkIdentity(ctx, env, join, capture);
  if (ctx.checks.slice(identityBefore).some((c) => !c.ok)) {
    ctx.aborted = true;
    return;
  }
  if (!checkJoinBinding(ctx, join, unitsRef, unitsBuf, units)) return;
  if (!pinJoinSupportArtifacts(ctx, env) || ctx.aborted) return;
  if (!checkSupportSchemas(ctx, env) || ctx.aborted) return;

  const boxes = [];
  for (const box of join.boxes) {
    const buf = readArtifact(ctx, box.path);
    if (!buf || ctx.aborted) return;
    checkPin(ctx, box.path, buf, box.sha256);
    const rows = parseJsonlArtifact(ctx, box.path, buf);
    if (!rows || ctx.aborted) return;
    boxes.push({ box, rows, buf });
  }

  const assignments = checkJoinAssignments(ctx, env, join, units, unitsRef, unitsBuf);
  if (!assignments || ctx.aborted) return;
  if (!validateJoinRows(ctx, boxes)) return;
  if (!checkJoinOrder(ctx, boxes, assignments)) return;
  if (!checkJoinPairs(ctx, claims, boxes)) return;
  if (!checkJoinWitness(ctx, units, unitsCtx.payloads, boxes)) return;
  if (!checkJoinClaimList(ctx, env, join, assignments, claims)) return;

  checkJoinBudget(ctx, env, boxes, assignments, unitsCtx.payloads);
  checkJoinRecovery(ctx, env, join, assignments);
  checkJoinMerge(ctx, join, boxes);
  checkJoinP05(ctx, env, boxes, claims);
  checkJoinCandidates(ctx, join, boxes, units);
}

// ---------------------------------------------------------------------------
// entry point
// ---------------------------------------------------------------------------

function main() {
  const argv = process.argv.slice(2);
  const parsed = parseCli(argv);
  if (!parsed.ok) {
    finish("usage", null, [{ name: "cli", ok: false, detail: USAGE, code: 2 }], 2, parsed.reason);
    return;
  }
  const ctx = new Ctx(path.resolve(parsed.runRoot));
  ctx.ok("cli", USAGE);
  try {
    if (parsed.command === "claims") runClaims(ctx);
    else if (parsed.command === "units") runUnits(ctx);
    else runJoin(ctx);
  } catch (err) {
    const message = firstLine(err?.message ?? String(err)).replaceAll(ctx.runRoot, "<run-root>");
    ctx.stop("runtime", `internal error: ${message}`);
  }
  finish(parsed.command, ctx.primarySchema, ctx.checks, ctx.exitCode, null);
}

main();
