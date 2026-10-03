#!/usr/bin/env node
// cure-light Phase-0 chunker — fixed windows at logical boundaries (block-end preferred).
//
//   node kernel/tools/chunker.mjs <repo> <base> <subject> <outDir>
//     → <outDir>/units2/manifest.json + units2/uNNNN.txt payloads
//
// Contract: kernel/references/chunker.md. Zero dependencies beyond Node + git.
// Fail-fast: usage errors, git/IO errors and lines that cannot fit the ceiling
// are hard errors; the runner never splits mid-line and never writes a manifest
// for a failed run.
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [, , repo, base, subject, outDir] = process.argv;
if (!repo || !base || !subject || !outDir) {
  console.error("usage: chunker.mjs <repo> <base> <subject> <outDir>");
  process.exit(2);
}

const TARGET = 4096; // preferred window size in bytes
const CEIL = 6144;   // hard ceiling for code windows
const CONTEXT = 3;    // unified diff context lines
const DEF_START = /^(?:async\s+def|def|class|function|export|const|let|var|public|private|protected|static|interface|type|enum|func|package|module|impl|struct|fn)\b/;
const strip = (l) => (l[0] === "+" || l[0] === "-" || l[0] === " " ? l.slice(1) : l);
const isBlank = (l) => /^\s*$/.test(strip(l)) || l.startsWith("\\ No newline");
const isDef = (l) => DEF_START.test(strip(l));

const fail = (msg) => { console.error(`chunker: ${msg}`); process.exit(1); };

// Two-dot diff, no renames, no external diffs/textconv (subject-configured
// filters are subject-tree executables and are never run), stable paths.
// The recipe is pinned against subject/runner git config: explicit prefixes
// defeat diff.noprefix/srcPrefix/dstPrefix, GIT_DIFF_OPTS is cleared (it
// overrides -U), submodules are always rendered so a committed ignore=all
// cannot hide a pointer change, and blank-empty/hunk-context config cannot
// move payload bytes or hunk boundaries.
let diff;
try {
  diff = execFileSync("git", [
    "-C", repo, "-c", "core.quotepath=false",
    "-c", "diff.suppressBlankEmpty=false",
    "diff", `-U${CONTEXT}`, "--src-prefix=a/", "--dst-prefix=b/",
    "--inter-hunk-context=0", "--submodule=short", "--ignore-submodules=none",
    "--no-ext-diff", "--no-color", "--no-renames",
    "--no-textconv", "--diff-algorithm=myers", `${base}..${subject}`,
  ], { maxBuffer: 1 << 28, env: { ...process.env, GIT_DIFF_OPTS: "" } }).toString("utf8");
} catch (err) {
  fail(`git diff failed: ${err.message}`);
}

const diffLines = diff.split("\n");
if (diffLines[diffLines.length - 1] === "") diffLines.pop(); // single terminal "" from git's final newline
const blocks = []; let cur = null;
for (const line of diffLines) {
  if (line.startsWith("diff --git ")) { if (cur) blocks.push(cur); cur = { header: line, lines: [] }; }
  else if (cur) cur.lines.push(line);
}
if (cur) blocks.push(cur);

// --no-renames means both sides name the same path. The text header is
// ambiguous when the path itself contains " b/"; recover it by comparing
// the a-side and b-side spans after the full `diff --git a/` prefix and
// keeping the longest equal match. Fall back to the raw header when no
// split makes both sides equal (e.g. a C-quoted path).
const DIFF_PREFIX = "diff --git a/";
const parseDiffPath = (header) => {
  if (!header.startsWith(DIFF_PREFIX)) return header;
  const rest = header.slice(DIFF_PREFIX.length);
  let best = null, p = rest.indexOf(" b/");
  while (p !== -1) {
    const left = rest.slice(0, p), right = rest.slice(p + 3);
    if (left.length > 0 && left === right && (best === null || left.length > best.length)) best = left;
    p = rest.indexOf(" b/", p + 1);
  }
  return best === null ? header : best;
};

// Exact stored payload size: a unit is written as lines.join("\n") with no
// trailing newline, and byte_len must match those bytes.
const bytes = (arr) => Buffer.byteLength(arr.join("\n"), "utf8");

const units = []; let uid = 0;
try { mkdirSync(join(outDir, "units2"), { recursive: true }); }
catch (err) { fail(`cannot create output directory: ${err.message}`); }

const flush = (filePath, buf, ranges, boundary) => {
  if (!buf.length) return;
  if (boundary.kind !== "file" && bytes(buf) > CEIL) {
    fail(`internal window overflow (${bytes(buf)} bytes > ${CEIL}) in ${filePath}`);
  }
  const id = `u${String(uid).padStart(4, "0")}`;
  try { writeFileSync(join(outDir, "units2", `${id}.txt`), buf.join("\n"), "utf8"); }
  catch (err) { fail(`cannot write unit payload ${id}.txt: ${err.message}`); }
  units.push({
    unit_id: id, file: `units2/${id}.txt`, path: filePath,
    ranges, hunk_count: ranges.length, byte_len: bytes(buf),
    blocks: boundary.blocks, boundary_kind: boundary.kind,
  });
  uid += 1;
};

// Split a hunk's lines into logical blocks.
function toBlocks(lines) {
  const hasDef = lines.some(isDef);
  const out = []; let b = [];
  if (hasDef) {
    for (const l of lines) { if (isDef(l) && b.length) { out.push(b); b = []; } b.push(l); }
    if (b.length) out.push(b);
  } else {
    for (const l of lines) {
      if (isBlank(l)) { b.push(l); continue; }
      if (b.length && b.some((x) => !isBlank(x)) && isBlank(b[b.length - 1]) && !isBlank(l)) { out.push(b); b = []; }
      b.push(l);
    }
    if (b.length) out.push(b);
  }
  return out.filter((x) => x.length);
}
const splitByLines = (lines, cap) => { const out = []; let p = []; for (const l of lines) { if (p.length && bytes(p.concat([l])) > cap) { out.push(p); p = []; } p.push(l); } if (p.length) out.push(p); return out; };

for (const block of blocks) {
  const filePath = parseDiffPath(block.header);
  const preamble = []; const hunks = []; let h = null;
  for (const line of block.lines) {
    if (line.startsWith("@@")) {
      if (h) hunks.push(h);
      const r = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/);
      h = { header: line, lines: [], old_start: r ? +r[1] : null, old_count: r && r[2] != null ? +r[2] : 1, new_start: r ? +r[3] : null, new_count: r && r[4] != null ? +r[4] : 1 };
    } else if (h) h.lines.push(line); else preamble.push(line);
  }
  if (h) hunks.push(h);
  // No-hunk file surfaces stay visible as one `file` metadata unit; they are
  // not code windows and are exempt from the window ceiling.
  if (!hunks.length) { flush(filePath, preamble.length ? preamble : [block.header], [], { blocks: 1, kind: "file" }); continue; }

  let buf = [], ranges = [], nblocks = 0;
  const flushBuf = () => {
    flush(filePath, buf, ranges, { blocks: nblocks, kind: "block" });
    buf = []; ranges = []; nblocks = 0;
  };
  hunks.forEach((hunk, i) => {
    const range = { old_start: hunk.old_start, old_count: hunk.old_count, new_start: hunk.new_start, new_count: hunk.new_count };
    const lines = (i === 0 ? preamble : []).concat([hunk.header], hunk.lines);
    const hb = bytes(lines);
    if (bytes(buf) + hb <= CEIL) { buf = buf.concat(lines); ranges.push(range); nblocks += 1; if (bytes(buf) >= TARGET) flushBuf(); return; }
    if (buf.length) flushBuf();
    if (hb <= CEIL) { buf = lines.slice(); ranges = [range]; nblocks = 1; if (bytes(buf) >= TARGET) flushBuf(); return; }
    // Oversized hunk: block-level split first, line fallback only for a single
    // block that cannot fit; never split mid-line.
    const inner = toBlocks(lines);
    const whole = inner.filter((b) => bytes(b) <= CEIL);
    if (whole.length === inner.length) {
      for (const b of inner) {
        if (bytes(buf) + bytes(b) > CEIL && buf.length) flushBuf();
        buf = buf.concat(b); ranges.push(range); nblocks += 1;
        if (bytes(buf) >= TARGET) flushBuf();
      }
    } else {
      for (const b of inner) {
        if (bytes(b) <= CEIL) {
          if (bytes(buf) + bytes(b) > CEIL && buf.length) flushBuf();
          buf = buf.concat(b); ranges.push(range); nblocks += 1;
          if (bytes(buf) >= TARGET) flushBuf();
        } else {
          if (buf.length) flushBuf(); // diff order: pending earlier bytes are emitted first
          for (const p of splitByLines(b, TARGET)) {
            if (bytes(p) > CEIL) fail(`indivisible line exceeds the ${CEIL}-byte ceiling in ${filePath}; refusing to split mid-line`);
            flush(filePath, p, [range], { blocks: 1, kind: "line-split" });
          }
        }
      }
    }
  });
  if (buf.length) flushBuf();
}

const manifest = {
  schema_version: "code-units-sim/2",
  recipe: { chunker: "chunker.mjs", target_bytes: TARGET, ceiling_bytes: CEIL, context: CONTEXT, block_preference: true },
  identity: {
    repo, base_ref: base, subject_ref: subject,
    base_oid: execFileSync("git", ["-C", repo, "rev-parse", base]).toString().trim(),
    subject_oid: execFileSync("git", ["-C", repo, "rev-parse", subject]).toString().trim(),
  },
  counts: { units: units.length, files: blocks.length, line_split_units: units.filter((u) => u.boundary_kind === "line-split").length, total_bytes: units.reduce((n, u) => n + u.byte_len, 0) },
  units,
};
try { writeFileSync(join(outDir, "units2", "manifest.json"), JSON.stringify(manifest, null, 1), "utf8"); }
catch (err) { fail(`cannot write manifest: ${err.message}`); }
console.log(JSON.stringify(manifest.counts));
console.log(units.map((u) => `${u.unit_id} ${String(u.byte_len).padStart(6)}B blocks=${u.blocks} ${u.boundary_kind.padEnd(10)} ${u.path}`).join("\n"));
