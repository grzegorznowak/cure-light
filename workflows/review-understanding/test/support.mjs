import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const WORKFLOW = join(ROOT, 'review-understanding.js');
export const SKILLS = ['review-understanding-summary', 'review-understanding-splits', 'check-tests-soundness'];
export const PR = 'https://github.com/example/project/pull/42';
export const skillText = (name) => readFileSync(join(ROOT, 'skills', name, 'SKILL.md'), 'utf8');

export const understanding = {
  summary: 'Add session expiry and document its configuration.',
  base_sha: 'a'.repeat(40), head_sha: 'b'.repeat(40), coverage: 'complete',
  sources: [
    { url: PR, kind: 'pr', status: 'read', note: 'PR description.' },
    { url: 'https://github.com/example/project/issues/7', kind: 'issue', status: 'read', note: 'Expiry requirement.' },
    { url: `${PR}/files`, kind: 'diff', status: 'read', note: 'Full changeset.' },
  ],
  domains: [{ name: 'Sessions', intent: 'Expire idle sessions.', changes: ['Enforce a configurable idle limit.'], files: ['src/session.js', 'test/session.test.js', 'README.md'], issues: ['https://github.com/example/project/issues/7'], evidence: ['src/session.js:10-20', 'Issue #7 acceptance criteria'] }],
  limitations: [],
};

export const splits = 'Keep expiry code, its tests and configuration docs together; no useful split.';
export const defaultRunStub = (_prompt, _options, { calls }) => calls.run.length === 1
  ? { output: understanding, text: 'Not the structured result.' }
  : { text: splits };

// Build isolated model-group config fixtures. Both env overrides are always set so
// tests do not depend on the real global or project config on the host.
// `project`/`global` map group names to member counts; `corrupt` makes the project
// file invalid JSON. `missingGlobal` points the global override at a nonexistent file.
export function modelGroupsEnv({ project = { 'code-review': 1, plan: 1 }, global = null, corrupt = false, missingGlobal = false } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'review-groups-'));
  const env = {};
  const write = (name, counts) => {
    const groups = {};
    for (const [group, n] of Object.entries(counts)) groups[group] = { models: Array.from({ length: n }, (_, i) => ({ provider: 'p', modelId: `m${i}` })) };
    const file = join(dir, `${name}.json`);
    writeFileSync(file, corrupt ? '{ this is not json' : JSON.stringify({ version: 2, groups }, null, 2));
    return file;
  };
  if (project) env.REVIEW_UNDERSTANDING_PROJECT_GROUPS = write('project', project);
  if (global) env.REVIEW_UNDERSTANDING_GLOBAL_GROUPS = write('global', global);
  if (missingGlobal) env.REVIEW_UNDERSTANDING_GLOBAL_GROUPS = join(dir, 'missing-global.json');
  return { dir, env };
}
