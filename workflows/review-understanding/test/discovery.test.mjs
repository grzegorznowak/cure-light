import test from 'node:test';
import assert from 'node:assert/strict';
import { lstatSync, mkdtempSync, realpathSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { isAbsolute, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { install } from '../install.mjs';
import { ROOT, SKILLS } from './support.mjs';

// Optional, offline, without launching Pi or scanning user directories:
// REVIEW_UNDERSTANDING_SKILL_LOADER=/absolute/pi-coding-agent/dist/core/skills.js \
// node --test test/discovery.test.mjs
// Use the real installed module at an explicit path; no copied parser, live/global
// installation or Pi/model launch.
const loaderPath = process.env.REVIEW_UNDERSTANDING_SKILL_LOADER;
test('actual selected Pi loader discovers both skills through installed project symlinks', {
  skip: loaderPath ? false : 'Set REVIEW_UNDERSTANDING_SKILL_LOADER to opt into native offline skill discovery.',
}, async () => {
  assert.ok(isAbsolute(loaderPath), 'Use an absolute installed Pi skill-loader path.');
  const { loadSkillsFromDir, formatSkillsForPrompt } = await import(pathToFileURL(loaderPath).href);
  assert.equal(typeof loadSkillsFromDir, 'function');
  const project = mkdtempSync(join(tmpdir(), 'review-understanding-discovery-'));
  const packageRoot = realpathSync(ROOT);
  const result = install({ project });
  assert.equal(result.project, realpathSync(project));
  assert.equal(result.links.length, 3);
  assert.ok(result.links.every((link) => link.status === 'linked'));
  const dir = join(project, '.pi/skills');
  for (const name of SKILLS) {
    const destination = join(dir, name);
    assert.ok(lstatSync(destination).isSymbolicLink(), destination);
    assert.equal(realpathSync(destination), join(packageRoot, 'skills', name));
  }
  const { skills, diagnostics } = loadSkillsFromDir({ dir, source: 'project' });
  assert.deepEqual(skills.map((skill) => skill.name).sort(), [...SKILLS].sort());
  assert.deepEqual(diagnostics, []);
  const prompt = formatSkillsForPrompt(skills);
  for (const skill of skills) {
    const sourceDir = join(packageRoot, 'skills', skill.name);
    assert.equal(realpathSync(skill.filePath), join(sourceDir, 'SKILL.md'));
    assert.equal(realpathSync(skill.baseDir), sourceDir);
    assert.ok(skill.description.trim().length > 0);
    assert.equal(skill.disableModelInvocation, false);
    assert.equal(skill.sourceInfo.scope, 'project');
    assert.ok(prompt.includes(`<name>${skill.name}</name>`));
    assert.ok(prompt.includes(skill.filePath));
  }
});
