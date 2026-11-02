import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, readlinkSync, realpathSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, isAbsolute, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { install } from '../install.mjs';
import { ROOT, SKILLS } from './support.mjs';

const PACKAGE = realpathSync(ROOT);
const INSTALLER = join(PACKAGE, 'install.mjs');
const NAMES = ['review-understanding-summary', 'review-understanding-splits'];
const project = () => mkdtempSync(join(tmpdir(), 'review-understanding-install-'));
const cli = (args, cwd = PACKAGE) => spawnSync(process.execPath, [INSTALLER, ...args], {
  cwd, encoding: 'utf8', timeout: 10_000,
});

function verifyLinks(root, result) {
  assert.equal(result.project, realpathSync(root));
  assert.equal(result.links.length, 3);
  const expected = [
    [join(root, '.pi/workflows/review-understanding.js'), join(PACKAGE, 'review-understanding.js')],
    ...NAMES.map((name) => [join(root, '.pi/skills', name), join(PACKAGE, 'skills', name)]),
  ];
  for (const [destination, source] of expected) {
    assert.ok(lstatSync(destination).isSymbolicLink());
    assert.equal(isAbsolute(readlinkSync(destination)), false, 'Discovery link is relative.');
    assert.equal(realpathSync(destination), source);
    assert.ok(result.links.some((link) => link.source === source && link.destination === destination));
  }
}

test('install once, rerun without changing links, preserve unrelated project assets', () => {
  const root = project();
  const unrelated = join(root, '.pi/skills/unrelated/SKILL.md');
  mkdirSync(dirname(unrelated), { recursive: true });
  writeFileSync(unrelated, 'keep this resource');
  const first = install({ project: root });
  verifyLinks(root, first);
  assert.ok(first.links.every((link) => link.status === 'linked'));
  const prior = first.links.map((link) => lstatSync(link.destination));
  const second = install({ project: root });
  verifyLinks(root, second);
  assert.ok(second.links.every((link) => link.status === 'existing'));
  for (const [index, link] of second.links.entries()) {
    const current = lstatSync(link.destination);
    assert.equal(current.ino, prior[index].ino);
    assert.equal(current.mtimeMs, prior[index].mtimeMs);
  }
  assert.equal(readFileSync(unrelated, 'utf8'), 'keep this resource');
});

test('dry-run makes no discovery folders, then reports existing links after install', () => {
  const root = project();
  const result = install({ project: root, dryRun: true });
  assert.equal(result.dryRun, true);
  assert.ok(result.links.every((link) => link.status === 'planned'));
  assert.deepEqual(readdirSync(root), []);
  install({ project: root });
  assert.ok(install({ project: root, dryRun: true }).links.every((link) => link.status === 'existing'));
});

for (const kind of ['file', 'directory', 'wrong-link', 'broken-link', 'loop-link', 'identical-copy']) {
  test(`last skill ${kind} conflict prevents every new link`, () => {
    const root = project();
    const destination = join(root, '.pi/skills/review-understanding-splits');
    mkdirSync(dirname(destination), { recursive: true });
    if (kind === 'file') writeFileSync(destination, 'preserve');
    if (kind === 'directory' || kind === 'identical-copy') {
      mkdirSync(destination);
      writeFileSync(join(destination, 'SKILL.md'), kind === 'identical-copy'
        ? readFileSync(join(PACKAGE, 'skills/review-understanding-splits/SKILL.md')) : 'preserve');
    }
    if (kind === 'wrong-link') symlinkSync(join(PACKAGE, 'skills/review-understanding-summary'), destination);
    if (kind === 'broken-link') symlinkSync('missing-skill', destination);
    if (kind === 'loop-link') symlinkSync('review-understanding-splits', destination);
    const before = lstatSync(destination);
    assert.throws(() => install({ project: root }), /refusing to replace existing asset/);
    assert.equal(lstatSync(destination).ino, before.ino, `${kind}: destination untouched`);
    assert.equal(existsSync(join(root, '.pi/workflows/review-understanding.js')), false, `${kind}: no partial install`);
  });
}

test('respects a project workflows directory that already contains an unrelated workflow', () => {
  const root = project();
  const workflows = join(root, '.pi/workflows');
  mkdirSync(workflows, { recursive: true });
  writeFileSync(join(workflows, 'other.js'), 'module.exports = 1;');
  const result = install({ project: root });
  verifyLinks(root, result);
  assert.equal(readFileSync(join(workflows, 'other.js'), 'utf8'), 'module.exports = 1;');
});

test('CLI supports --help and --dry-run and rejects unknown flags without writing', () => {
  const help = cli(['--help']);
  assert.equal(help.status, 0);
  assert.match(help.stdout, /--dry-run/);
  const root = project();
  const dry = cli(['--dry-run'], root);
  assert.equal(dry.status, 0);
  assert.match(dry.stdout, /planned:/);
  assert.deepEqual(readdirSync(root), []);
  const bad = cli(['--force'], root);
  assert.equal(bad.status, 1);
  assert.match(bad.stderr, /Invalid argument/);
  assert.deepEqual(readdirSync(root), []);
});
