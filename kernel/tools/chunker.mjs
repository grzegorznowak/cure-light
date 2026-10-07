#!/usr/bin/env node
// cure-light Phase-0 chunker — fixed windows at logical boundaries (block-end preferred).
//
//   node kernel/tools/chunker.mjs <repo> <base> <subject> <outDir>
//     → <outDir>/units2/manifest.json + units2/uNNNN.txt payloads
//
// Contract: kernel/references/chunker.md. Zero dependencies beyond Node + git.
// Over-ceiling diff lines never enter model-facing payloads: their bodies are
// captured pre-decode into the machine-only units2/raw/occ-NNNN.bin store and
// summarized by bounded opaque-descriptor units (code-units-sim/3). Git's
// optional hunk-header section text is stripped whenever it copies bytes from
// such a body.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [, , repo, base, subject, outDir] = process.argv;
if (!repo || !base || !subject || !outDir) {
  console.error("usage: chunker.mjs <repo> <base> <subject> <outDir>");
  process.exit(2);
}

const TARGET = 4096;
const CEIL = 6144;
const CONTEXT = 3;
const OPAQUE_DESCRIPTOR_MAX_BYTES = 1024;
const DEF_START = /^(?:async\s+def|def|class|function|export|const|let|var|public|private|protected|static|interface|type|enum|func|package|module|impl|struct|fn)\b/;
const strip = (l) => (l[0] === "+" || l[0] === "-" || l[0] === " " ? l.slice(1) : l);
const isBlank = (l) => /^\s*$/.test(strip(l)) || l.startsWith("\\ No newline");
const isDef = (l) => DEF_START.test(strip(l));
const fail = (msg) => { console.error(`chunker: ${msg}`); process.exit(1); };
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

// Two-dot diff, no renames, no external diffs/textconv (subject-configured
// filters are subject-tree executables and are never run), stable paths.
let rawDiff;
try {
  rawDiff = execFileSync("git", [
    "-C", repo, "-c", "core.quotepath=false",
    "-c", "diff.suppressBlankEmpty=false",
    "diff", `-U${CONTEXT}`, "--src-prefix=a/", "--dst-prefix=b/",
    "--inter-hunk-context=0", "--submodule=short", "--ignore-submodules=none",
    "--no-ext-diff", "--no-color", "--no-renames",
    "--no-textconv", "--diff-algorithm=myers", `${base}..${subject}`,
  ], { maxBuffer: 1 << 28, env: { ...process.env, GIT_DIFF_OPTS: "" } });
} catch (err) {
  fail(`git diff failed: ${err.message}`);
}

// Preserve a pre-decode counterpart for every decoded line. Splitting only on
// LF mirrors String#split("\n") while retaining CR and invalid UTF-8 bytes.
const rawLines = [];
for (let start = 0, i = 0; i < rawDiff.length; i += 1) {
  if (rawDiff[i] === 0x0a) {
    rawLines.push(rawDiff.subarray(start, i));
    start = i + 1;
  }
  if (i + 1 === rawDiff.length && start < rawDiff.length) rawLines.push(rawDiff.subarray(start));
}
const diffLines = rawDiff.toString("utf8").split("\n");
if (diffLines[diffLines.length - 1] === "") diffLines.pop();
const blocks = []; let cur = null;
for (let i = 0; i < diffLines.length; i += 1) {
  const line = diffLines[i];
  if (line.startsWith("diff --git ")) {
    if (cur) blocks.push(cur);
    cur = { header: line, lines: [] };
  } else if (cur) {
    cur.lines.push({ line, raw: rawLines[i] });
  }
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
const occurrences = [];
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

const opaqueBodies = [];
const addOpaqueOccurrence = (filePath, raw) => {
  const marker = String.fromCharCode(raw[0]);
  const side = marker === "-" ? "removed" : marker === "+" ? "added" : "context";
  const occurrence_id = `occ-${String(occurrences.length).padStart(4, "0")}`;
  const body = raw.subarray(1);
  const entry = {
    occurrence_id, path: filePath, side, byte_length: body.length, sha256: sha256(body),
    ref: `units2/raw/${occurrence_id}.bin`, pair_id: null, state: side === "context" ? "context" : "unpaired",
  };
  try {
    mkdirSync(join(outDir, "units2", "raw"), { recursive: true });
    writeFileSync(join(outDir, entry.ref), body);
  } catch (err) {
    fail(`cannot write raw occurrence ${occurrence_id}.bin: ${err.message}`);
  }
  opaqueBodies.push(Buffer.from(body));
  occurrences.push(entry);
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
const splitByLines = (lines, cap) => {
  const out = []; let p = [];
  for (const l of lines) { if (p.length && bytes(p.concat([l])) > cap) { out.push(p); p = []; } p.push(l); }
  if (p.length) out.push(p);
  return out;
};

// Pass 1: classify opaque lines out of every hunk before any payload is
// emitted. A hunk-header section (the trailing `@@ <function>` text) can copy
// bytes from an over-ceiling line, so header sanitization must see every
// occurrence body, including ones collected by later blocks.
const blocksReview = [];
for (const block of blocks) {
  const filePath = parseDiffPath(block.header);
  const preamble = []; const hunks = []; let h = null;
  for (const entry of block.lines) {
    const { line } = entry;
    if (line.startsWith("@@")) {
      if (h) hunks.push(h);
      const r = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/);
      h = { header: line, headerRaw: entry.raw, lines: [], old_start: r ? +r[1] : null, old_count: r && r[2] != null ? +r[2] : 1, new_start: r ? +r[3] : null, new_count: r && r[4] != null ? +r[4] : 1 };
    } else if (h) h.lines.push(entry); else preamble.push(line);
  }
  if (h) hunks.push(h);
  for (const hunk of hunks) {
    hunk.reviewLines = hunk.lines.filter((entry) => {
      const opaque = entry.raw.length > CEIL && (entry.raw[0] === 0x2b || entry.raw[0] === 0x2d || entry.raw[0] === 0x20);
      if (opaque) addOpaqueOccurrence(filePath, entry.raw);
      return !opaque;
    }).map((entry) => entry.line);
  }
  blocksReview.push({ header: block.header, filePath, preamble, hunks });
}

// The optional section text after the closing `@@` is copied verbatim from a
// subject line; strip it from any header whose section appears inside a
// machine-only occurrence body (never model input).
const SECTION_MARK = Buffer.from("@@");
for (const block of blocksReview) {
  for (const hunk of block.hunks) {
    const stop = hunk.headerRaw.indexOf(SECTION_MARK, 2);
    let section = stop === -1 ? Buffer.alloc(0) : hunk.headerRaw.subarray(stop + SECTION_MARK.length);
    if (section[0] === 0x20) section = section.subarray(1);
    if (section.length && opaqueBodies.some((body) => body.includes(section))) {
      const prefix = hunk.header.match(/^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@/);
      if (prefix) hunk.reviewHeader = prefix[0];
    }
  }
}

for (const block of blocksReview) {
  const { filePath, preamble, hunks } = block;
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
    const lines = (i === 0 ? preamble : []).concat([hunk.reviewHeader ?? hunk.header], hunk.reviewLines);
    const hb = bytes(lines);
    if (bytes(buf) + hb <= CEIL) { buf = buf.concat(lines); ranges.push(range); nblocks += 1; if (bytes(buf) >= TARGET) flushBuf(); return; }
    if (buf.length) flushBuf();
    if (hb <= CEIL) { buf = lines.slice(); ranges = [range]; nblocks = 1; if (bytes(buf) >= TARGET) flushBuf(); return; }
    // Oversized hunk: block-level split first, line fallback only for a single
    // block that cannot fit; never split mid-line. Opaque lines have already
    // been removed, so this is an unreachable safety net for their old error.
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
          if (buf.length) flushBuf();
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

const pairGroups = new Map();
for (const entry of occurrences) {
  if (entry.side === "context") continue;
  if (!pairGroups.has(entry.sha256)) pairGroups.set(entry.sha256, []);
  pairGroups.get(entry.sha256).push(entry);
}
let pairNumber = 0;
const ambiguous = [];
for (const group of pairGroups.values()) {
  const removed = group.filter((entry) => entry.side === "removed");
  const added = group.filter((entry) => entry.side === "added");
  if (removed.length === 1 && added.length === 1) {
    const pair_id = `pair-${String(pairNumber).padStart(4, "0")}`;
    pairNumber += 1;
    for (const entry of group) { entry.pair_id = pair_id; entry.state = "paired"; }
  } else if (removed.length && added.length) {
    for (const entry of group) { entry.state = "ambiguous"; ambiguous.push(entry.occurrence_id); }
  }
}
// Leftover non-identical removals/additions are only evidence of a failed move
// when they plausibly belong to the same move: zip them per file, never across
// unrelated files.
const leftoverRemoved = occurrences.filter((entry) => entry.side === "removed" && entry.state === "unpaired");
const leftoverAdded = occurrences.filter((entry) => entry.side === "added" && entry.state === "unpaired");
const leftoversByPath = new Map();
for (const entry of [...leftoverRemoved, ...leftoverAdded]) {
  if (!leftoversByPath.has(entry.path)) leftoversByPath.set(entry.path, { removed: [], added: [] });
  leftoversByPath.get(entry.path)[entry.side].push(entry);
}
const notByteEqual = [];
const unpaired = [];
for (const group of leftoversByPath.values()) {
  const common = Math.min(group.removed.length, group.added.length);
  for (let i = 0; i < common; i += 1) {
    notByteEqual.push(group.removed[i].occurrence_id, group.added[i].occurrence_id);
  }
  unpaired.push(
    ...group.removed.slice(common).map((entry) => entry.occurrence_id),
    ...group.added.slice(common).map((entry) => entry.occurrence_id),
  );
}
const occurrenceIndex = new Map(occurrences.map((entry, index) => [entry.occurrence_id, index]));
const inManifestOrder = (ids) => ids.sort((left, right) => occurrenceIndex.get(left) - occurrenceIndex.get(right));
const skips = [];
for (const [reason, occurrence_ids] of [["ambiguous", ambiguous], ["not-byte-equal", notByteEqual], ["unpaired", unpaired]]) {
  if (occurrence_ids.length) skips.push({ skip_id: `skip-${String(skips.length).padStart(4, "0")}`, reason, occurrence_ids: inManifestOrder(occurrence_ids) });
}

const descriptorPayload = (id, entries) => {
  const occurrence_ids = new Set(entries.map((entry) => entry.occurrence_id));
  const pairing = [];
  const seenPairs = new Set();
  for (const entry of entries) {
    if (!entry.pair_id || seenPairs.has(entry.pair_id)) continue;
    const members = occurrences.filter((candidate) => candidate.pair_id === entry.pair_id);
    if (members.every((member) => occurrence_ids.has(member.occurrence_id))) {
      pairing.push({ pair_id: entry.pair_id, occurrence_ids: members.map((member) => member.occurrence_id) });
      seenPairs.add(entry.pair_id);
    }
  }
  return JSON.stringify({
    schema: "opaque-descriptor/1", unit_id: id,
    occurrences: entries.map(({ occurrence_id, side, byte_length, sha256: digest }) => ({ occurrence_id, side, byte_length, sha256: digest })),
    pairing,
  });
};
const writeDescriptor = (entries) => {
  const id = `u${String(uid).padStart(4, "0")}`;
  const payload = descriptorPayload(id, entries);
  if (Buffer.byteLength(payload, "utf8") > OPAQUE_DESCRIPTOR_MAX_BYTES) fail(`opaque descriptor ${id}.txt exceeds ${OPAQUE_DESCRIPTOR_MAX_BYTES} bytes`);
  try { writeFileSync(join(outDir, "units2", `${id}.txt`), payload, "utf8"); }
  catch (err) { fail(`cannot write unit payload ${id}.txt: ${err.message}`); }
  units.push({ unit_id: id, file: `units2/${id}.txt`, path: entries[0].path, ranges: [], hunk_count: 0, byte_len: Buffer.byteLength(payload, "utf8"), blocks: 1, boundary_kind: "opaque" });
  uid += 1;
};
if (occurrences.length) {
  const groups = [];
  const seen = new Set();
  for (const entry of occurrences) {
    if (seen.has(entry.occurrence_id)) continue;
    const group = entry.pair_id
      ? occurrences.filter((candidate) => candidate.pair_id === entry.pair_id)
      : [entry];
    group.forEach((candidate) => seen.add(candidate.occurrence_id));
    groups.push(group);
  }
  let pending = [];
  for (const group of groups) {
    const candidate = pending.concat(group);
    const id = `u${String(uid).padStart(4, "0")}`;
    if (pending.length && Buffer.byteLength(descriptorPayload(id, candidate), "utf8") > OPAQUE_DESCRIPTOR_MAX_BYTES) {
      writeDescriptor(pending);
      pending = group;
    } else {
      pending = candidate;
    }
  }
  if (pending.length) writeDescriptor(pending);
}

const coverage = {
  status: skips.length ? "partial" : "complete",
  machine_occurrences: occurrences.length,
  skips: skips.map((skip) => skip.skip_id),
};
const manifest = {
  schema_version: "code-units-sim/3",
  recipe: { chunker: "chunker.mjs", target_bytes: TARGET, ceiling_bytes: CEIL, context: CONTEXT, block_preference: true },
  identity: {
    repo, base_ref: base, subject_ref: subject,
    base_oid: execFileSync("git", ["-C", repo, "rev-parse", base]).toString().trim(),
    subject_oid: execFileSync("git", ["-C", repo, "rev-parse", subject]).toString().trim(),
  },
  counts: {
    units: units.length, files: blocks.length,
    line_split_units: units.filter((u) => u.boundary_kind === "line-split").length,
    opaque_occurrences: occurrences.length,
    opaque_bytes: occurrences.reduce((sum, entry) => sum + entry.byte_length, 0),
    total_bytes: units.reduce((sum, unit) => sum + unit.byte_len, 0),
  },
  units, opaque_occurrences: occurrences, skips, coverage,
};
try { writeFileSync(join(outDir, "units2", "manifest.json"), JSON.stringify(manifest, null, 1), "utf8"); }
catch (err) { fail(`cannot write manifest: ${err.message}`); }
console.log(JSON.stringify(manifest.counts));
console.log(units.map((u) => `${u.unit_id} ${String(u.byte_len).padStart(6)}B blocks=${u.blocks} ${u.boundary_kind.padEnd(10)} ${u.path}`).join("\n"));
