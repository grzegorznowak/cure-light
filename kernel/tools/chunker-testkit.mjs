// cure-light chunker testkit — shared helpers for kernel/tools/chunker.test.mjs
// and chunker.paths.test.mjs. Zero dependencies beyond Node + git.
//
// CI recipe (ubuntu-latest, actions/setup-node + git are enough):
//
//   node --test "kernel/tools/*.test.mjs"
//
// On Node 22/24 a directory argument is not expanded by the test runner
// (`node --test kernel/tools/` fails with MODULE_NOT_FOUND); use the glob above.
//
// Every fixture repo is built at test time under os.tmpdir() with fixed author
// and committer dates, an isolated git config (GIT_CONFIG_GLOBAL/SYSTEM=/dev/null),
// and repo-local user.name/email, so manifests and payloads are reproducible.
// Golden updates:  UPDATE_GOLDENS=1 node --test "kernel/tools/*.test.mjs"
import { spawnSync } from "node:child_process";
import {
  existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync,
  writeFileSync, chmodSync, symlinkSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import assert from "node:assert/strict";

export const TOOLS_DIR = path.dirname(fileURLToPath(import.meta.url));
export const CHUNKER_PATH = path.join(TOOLS_DIR, "chunker.mjs");
export const FIXTURES_DIR = path.join(TOOLS_DIR, "test-fixtures");
export const TARGET_BYTES = 4096;
export const CEILING_BYTES = 6144;
export const CONTEXT_LINES = 3;
export const RECIPE = Object.freeze({
  chunker: "chunker.mjs",
  target_bytes: TARGET_BYTES,
  ceiling_bytes: CEILING_BYTES,
  context: CONTEXT_LINES,
  block_preference: true,
});
// Deterministic commit dates: any fixed instant inside git's supported range.
export const FIXED_DATE = "2001-02-03T04:05:06+00:00";
const DEV_NULL = process.platform === "win32" ? "NUL" : "/dev/null";

// Git session variables that must never leak from the invoking shell into the
// fixture builder or the chunker subprocess; a test may re-inject any of them
// explicitly through the `env` overrides.
const SESSION_VARS = [
  "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
  "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_PREFIX",
  "GIT_DIFF_OPTS",
];

/** Ambient env with git session vars stripped and fixture identity/isolation applied. */
export function cleanEnv(extra = {}) {
  const env = { ...process.env };
  for (const key of SESSION_VARS) delete env[key];
  return {
    ...env,
    GIT_CONFIG_GLOBAL: DEV_NULL,
    GIT_CONFIG_SYSTEM: DEV_NULL,
    GIT_TERMINAL_PROMPT: "0",
    GIT_AUTHOR_NAME: "cure-light fixture",
    GIT_AUTHOR_EMAIL: "fixture@cure-light.invalid",
    GIT_COMMITTER_NAME: "cure-light fixture",
    GIT_COMMITTER_EMAIL: "fixture@cure-light.invalid",
    GIT_AUTHOR_DATE: FIXED_DATE,
    GIT_COMMITTER_DATE: FIXED_DATE,
    ...extra,
  };
}

const tempDirs = new Set();

/** Allocate a unique directory under os.tmpdir(); removed by cleanupTempDirs(). */
export function tempDir(prefix) {
  const dir = mkdtempSync(path.join(os.tmpdir(), `cure-light-test-${prefix}-`));
  tempDirs.add(dir);
  return dir;
}

export function cleanupTempDirs() {
  for (const dir of tempDirs) {
    try { rmSync(dir, { recursive: true, force: true, maxRetries: 3 }); } catch { /* best effort */ }
  }
  tempDirs.clear();
}

/** Run a git command in `repo` with the isolated, deterministic fixture env. */
export function runGit(repo, args, { env = {}, input, check = true, maxBuffer = 1 << 26 } = {}) {
  const res = spawnSync("git", ["-C", repo, ...args], {
    encoding: "utf8", input, env: cleanEnv(env), maxBuffer,
  });
  if (check && res.status !== 0) {
    throw new Error(`git ${args.join(" ")} failed (status ${res.status})\nstdout:\n${res.stdout}\nstderr:\n${res.stderr}`);
  }
  return res;
}

/** Initialize a deterministic git repo (main branch, repo-local identity). */
export function initGitRepo(dir) {
  mkdirSync(dir, { recursive: true });
  runGit(dir, ["init", "-b", "main", "--quiet"]);
  runGit(dir, ["config", "user.name", "cure-light fixture"]);
  runGit(dir, ["config", "user.email", "fixture@cure-light.invalid"]);
  runGit(dir, ["config", "core.autocrlf", "false"]);
  return dir;
}

/** Fresh fixture repo: <tmp>/fixture-<name>/repo. */
export function createFixtureRepo(name) {
  return initGitRepo(path.join(tempDir(`fixture-${name}`), "repo"));
}

export function write(repo, rel, content) {
  const abs = path.join(repo, rel);
  mkdirSync(path.dirname(abs), { recursive: true });
  writeFileSync(abs, content);
  return abs;
}

export function read(repo, rel) {
  return readFileSync(path.join(repo, rel), "utf8");
}

export function stage(repo, ...paths) {
  runGit(repo, ["add", "--", ...paths]);
}

/** Stage the whole worktree (including deletions) and commit. */
export function commitAll(repo, message) {
  runGit(repo, ["add", "-A"]);
  runGit(repo, ["commit", "-m", message, "--quiet"]);
}

/** Commit exactly the current index (no `git add -A`); used for gitlink fixtures. */
export function commitIndex(repo, message) {
  runGit(repo, ["commit", "-m", message, "--quiet"]);
}

export function stageGitlink(repo, oid, subpath) {
  runGit(repo, ["update-index", "--add", "--cacheinfo", `160000,${oid},${subpath}`]);
}

export function branch(repo, name) {
  runGit(repo, ["checkout", "-b", name, "--quiet"]);
}

export function revParse(repo, ref) {
  return runGit(repo, ["rev-parse", ref]).stdout.trim();
}

export function setMode(repo, rel, mode) {
  chmodSync(path.join(repo, rel), mode);
}

export function symlink(repo, target, rel) {
  const abs = path.join(repo, rel);
  mkdirSync(path.dirname(abs), { recursive: true });
  symlinkSync(target, abs);
}

export function manifestPath(outDir) {
  return path.join(outDir, "units2", "manifest.json");
}

export function readManifest(outDir) {
  return JSON.parse(readFileSync(manifestPath(outDir), "utf8"));
}

/** Spawn the chunker exactly as the contract documents it. */
export function spawnChunker(args, { env = {}, cwd = os.tmpdir() } = {}) {
  return spawnSync(process.execPath, [CHUNKER_PATH, ...args], {
    encoding: "utf8", cwd, env: cleanEnv(env), maxBuffer: 1 << 26,
  });
}

/** Run the chunker on <repo> <base> <subject> <outDir>. */
export function runChunker({ repo, base = "main", subject = "subject", outDir, env = {}, cwd } = {}) {
  const dir = outDir ?? tempDir("out");
  const res = spawnChunker([repo, base, subject, dir], { env, cwd });
  return { ...res, repo, base, subject, outDir: dir };
}

/** The exact diff recipe the chunker pins, emitted verbatim by git. */
export function gitDiffRaw(repo, base = "main", subject = "subject", { env = {}, check = true } = {}) {
  const res = runGit(repo, [
    "-c", "core.quotepath=false",
    "-c", "diff.suppressBlankEmpty=false",
    "diff", `-U${CONTEXT_LINES}`, "--src-prefix=a/", "--dst-prefix=b/",
    "--inter-hunk-context=0", "--submodule=short", "--ignore-submodules=none",
    "--no-ext-diff", "--no-color", "--no-renames", "--no-textconv",
    "--diff-algorithm=myers", `${base}..${subject}`,
  ], { env: { GIT_DIFF_OPTS: "", ...env }, check });
  return res.stdout;
}

/** File order git would present in the diff (used to lock manifest order). */
export function gitChangedFileOrder(repo, base = "main", subject = "subject") {
  const res = runGit(repo, ["diff", "--name-only", "--no-renames", `${base}..${subject}`]);
  return res.stdout.split("\n").filter(Boolean);
}

export function normalizeManifest(manifest, repoPath) {
  const copy = structuredClone(manifest);
  if (copy.identity?.repo === repoPath) copy.identity.repo = "<REPO>";
  return copy;
}

/** Read a chunker run: normalized manifest + payload map (basename -> Buffer). */
export function readRunArtifacts(outDir, repoPath) {
  const manifest = normalizeManifest(readManifest(outDir), repoPath);
  const payloads = new Map();
  for (const unit of manifest.units) {
    payloads.set(path.basename(unit.file), readFileSync(path.join(outDir, unit.file)));
  }
  return { manifest, payloads };
}

export function goldenDir(name) {
  return path.join(FIXTURES_DIR, name, "expected");
}

/** Read a golden: manifest is stored already normalized (repo -> "<REPO>"). */
export function readGoldenArtifacts(name) {
  const dir = goldenDir(name);
  const manifest = JSON.parse(readFileSync(path.join(dir, "manifest.json"), "utf8"));
  const payloads = new Map();
  for (const unit of manifest.units) {
    const base = path.basename(unit.file);
    payloads.set(base, readFileSync(path.join(dir, base)));
  }
  return { manifest, payloads };
}

function hexAround(buf, offset) {
  const start = Math.max(0, offset - 8);
  const end = Math.min(buf.length, offset + 8);
  return `${buf.subarray(start, end).toString("hex")} (offset ${offset})`;
}

export function assertBytesEqual(actual, expected, label) {
  const a = Buffer.from(actual);
  const b = Buffer.from(expected);
  if (a.equals(b)) return;
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i += 1;
  assert.fail(`${label}: bytes differ at offset ${i} (actual ${a.length}B, expected ${b.length}B)\n  actual:   ${hexAround(a, i)}\n  expected: ${hexAround(b, i)}`);
}

function writeGolden(name, artifacts) {
  const dir = goldenDir(name);
  mkdirSync(dir, { recursive: true });
  for (const entry of readdirSync(dir)) {
    if (/^u\d{4}\.txt$/.test(entry)) rmSync(path.join(dir, entry));
  }
  writeFileSync(path.join(dir, "manifest.json"), `${JSON.stringify(artifacts.manifest, null, 1)}\n`);
  for (const [base, bytes] of artifacts.payloads) writeFileSync(path.join(dir, base), bytes);
}

/**
 * Compare a run against its golden. UPDATE_GOLDENS=1 rewrites the golden and
 * returns { updated: true }; otherwise compares normalized manifest + payload
 * bytes and returns { updated: false }.
 */
export function assertRunMatchesGolden(name, run) {
  const actual = readRunArtifacts(run.outDir, run.repo);
  if (process.env.UPDATE_GOLDENS === "1") {
    writeGolden(name, actual);
    return { updated: true };
  }
  let expected;
  try {
    expected = readGoldenArtifacts(name);
  } catch (err) {
    assert.fail(`[${name}] no readable golden under ${goldenDir(name)} (${err.message}); run UPDATE_GOLDENS=1 node --test "kernel/tools/*.test.mjs" to create it`);
  }
  assert.deepStrictEqual(actual.manifest, expected.manifest, `[${name}] normalized manifest differs from golden`);
  assert.deepStrictEqual(
    [...actual.payloads.keys()].sort(),
    [...expected.payloads.keys()].sort(),
    `[${name}] payload file set differs from golden`,
  );
  for (const base of expected.payloads.keys()) {
    assertBytesEqual(actual.payloads.get(base), expected.payloads.get(base), `[${name}] payload ${base}`);
  }
  return { updated: false };
}

/**
 * Contract invariants every successful run must satisfy (independent of
 * goldens). Throws on the first broken clause with the clause named.
 */
export function assertRunContract(run, { label = "" } = {}) {
  const prefix = label ? `[${label}] ` : "";
  assert.equal(run.status, 0, `${prefix}chunker exited ${run.status} (expected 0)\nstderr:\n${run.stderr}`);
  const manifest = readManifest(run.outDir);
  assert.equal(manifest.schema_version, "code-units-sim/2", `${prefix}schema_version`);
  assert.deepStrictEqual(manifest.recipe, RECIPE, `${prefix}recipe must be pinned exactly`);
  const units = manifest.units;
  assert.ok(Array.isArray(units), `${prefix}units[]`);
  assert.equal(manifest.counts.units, units.length, `${prefix}counts.units == units.length`);

  const payloadNames = readdirSync(path.join(run.outDir, "units2")).filter((n) => /^u\d{4}\.txt$/.test(n));
  assert.equal(payloadNames.length, units.length, `${prefix}counts.units == payload file count`);

  let totalBytes = 0;
  units.forEach((unit, i) => {
    assert.equal(unit.unit_id, `u${String(i).padStart(4, "0")}`, `${prefix}unit ids sequential at index ${i}`);
    assert.equal(unit.file, `units2/${unit.unit_id}.txt`, `${prefix}${unit.unit_id}.file`);
    assert.equal(unit.hunk_count, unit.ranges.length, `${prefix}${unit.unit_id} hunk_count == ranges.length`);
    const bytes = readFileSync(path.join(run.outDir, unit.file));
    assert.equal(bytes.length, unit.byte_len, `${prefix}${unit.unit_id} byte_len == payload size`);
    if (bytes.length > 0) {
      assert.notEqual(bytes[bytes.length - 1], 0x0a, `${prefix}${unit.unit_id} payload must not end with a trailing 0x0a`);
    }
    if (unit.boundary_kind !== "file") {
      assert.ok(unit.byte_len <= CEILING_BYTES, `${prefix}${unit.unit_id} code payload ${unit.byte_len}B exceeds ${CEILING_BYTES}B ceiling`);
    }
    totalBytes += unit.byte_len;
  });
  assert.equal(manifest.counts.total_bytes, totalBytes, `${prefix}counts.total_bytes == sum(byte_len)`);
  assert.equal(
    manifest.counts.line_split_units,
    units.filter((u) => u.boundary_kind === "line-split").length,
    `${prefix}counts.line_split_units == units.filter(line-split).length`,
  );
  return manifest;
}

/** Two runs of the same frozen fixture must be byte-identical modulo the repo path. */
export function assertRunsEquivalent(a, b, repoPath, label = "runs") {
  const left = readRunArtifacts(a.outDir, repoPath);
  const right = readRunArtifacts(b.outDir, repoPath);
  assert.deepStrictEqual(right.manifest, left.manifest, `${label}: normalized manifests differ`);
  assert.deepStrictEqual(
    [...right.payloads.keys()].sort(),
    [...left.payloads.keys()].sort(),
    `${label}: payload sets differ`,
  );
  for (const base of left.payloads.keys()) {
    assertBytesEqual(right.payloads.get(base), left.payloads.get(base), `${label}: payload ${base}`);
  }
}

export function discoverFixtures() {
  return readdirSync(FIXTURES_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && existsSync(path.join(FIXTURES_DIR, entry.name, "fixture.mjs")))
    .map((entry) => entry.name)
    .sort();
}

export async function loadFixture(name) {
  const mod = await import(pathToFileURL(path.join(FIXTURES_DIR, name, "fixture.mjs")).href);
  return { name, ...mod };
}

export async function buildFixture(name) {
  const mod = await loadFixture(name);
  if (typeof mod.build !== "function") throw new Error(`fixture ${name} does not export build(repo)`);
  const repo = createFixtureRepo(name);
  await mod.build(repo);
  return { name, repo, mod };
}
