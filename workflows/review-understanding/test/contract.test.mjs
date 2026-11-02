import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { runWorkflow } from './harness.mjs';
import { PR, ROOT, SKILLS, skillText, splits, understanding, WORKFLOW, modelGroupsEnv } from './support.mjs';

const run = (args = PR, overrides = {}) => {
  const { env = modelGroupsEnv({ missingGlobal: true }).env, ...rest } = overrides;
  return runWorkflow({
    file: WORKFLOW, args, env,
    runStub: (_prompt, _options, { calls }) => calls.run.length === 1
      ? { output: understanding, text: 'Not the structured result.' }
      : { text: splits },
    ...rest,
  });
};

test('structured default makes exactly two readonly runs and passes validated output explicitly', () => {
  const result = run();
  assert.equal(result.error, null);
  assert.equal(result.exit.reason, 'ok');
  assert.equal(result.calls.run.length, 2);
  assert.deepEqual(result.calls.run.map(call => call.readonly), [true, true]);
  const [first, second] = result.calls.run;
  assert.equal(first.options.input.pr_url, PR);
  assert.equal(first.options.output.schema.type, 'object');
  assert.deepEqual(second.options.input.understanding, understanding);
  assert.equal(second.options.input.pr_url, PR);
  assert.equal(second.options.input.format, 'structured');
  assert.equal(second.options.output, undefined, 'splitting stays a plain-text run');
  assert.deepEqual(result.exit.understanding, understanding);
  assert.equal(result.exit.splits, splits);
  assert.equal(result.exit.format, 'structured');
  assert.equal(result.calls.shell.length, 1, 'one model-group preflight shell call');
  assert.equal(result.calls.notebook.length, 0);
  assert.ok(result.calls.order.every(event => ['checkpoint', 'state', 'readonly', 'run', 'shell', 'exit'].includes(event.handle)));
  assert.deepEqual(result.calls.checkpoint.map(c => c.phase), ['ready', 'understood', 'split']);
  assert.deepEqual(result.calls.checkpoint[1].understanding, understanding, 'summary survives a later stop');
  assert.equal(result.calls.checkpoint[2].splits, splits);
});

test('--plain changes only first-run output format, not its substantive instructions', () => {
  const structured = run();
  const prose = 'Sessions: idle expiry implements issue #7; code, tests and docs change together.';
  const plain = run(`${PR} --plain`, {
    runStub: (_prompt, _options, { calls }) => ({ text: calls.run.length === 1 ? prose : splits }),
  });
  assert.equal(plain.error, null);
  assert.equal(plain.calls.run.length, 2);
  assert.equal(plain.calls.run[0].options.output, undefined);
  assert.equal(plain.calls.run[0].prompt, structured.calls.run[0].prompt);
  assert.equal(plain.calls.run[0].options.args, structured.calls.run[0].options.args);
  assert.deepEqual(plain.calls.run[0].options.input, structured.calls.run[0].options.input);
  assert.equal(plain.calls.run[1].options.input.understanding, prose);
  assert.equal(plain.exit.format, 'plain');
  assert.equal(plain.exit.understanding, prose);
});

test('the shipped model-groups config defines both required groups with members', () => {
  const shipped = JSON.parse(readFileSync(join(ROOT, '.pi', 'pi-schematic', 'model-groups.json'), 'utf8'));
  assert.equal(shipped.version, 2);
  for (const name of ['code-review', 'plan']) {
    assert.ok(shipped.groups[name], name);
    assert.ok(Array.isArray(shipped.groups[name].models) && shipped.groups[name].models.length >= 1, `${name}: at least one member`);
    for (const model of shipped.groups[name].models) {
      assert.ok(typeof model.provider === 'string' && model.provider, `${name}.provider`);
      assert.ok(typeof model.modelId === 'string' && model.modelId, `${name}.modelId`);
    }
  }
});

test('fails fast before any model run when a required group is missing', () => {
  const result = run(PR, { env: modelGroupsEnv({ project: { 'code-review': 1 }, missingGlobal: true }).env });
  assert.equal(result.error, null);
  assert.equal(result.exit.reason, 'needs-input');
  assert.deepEqual(result.exit.missing, ['plan']);
  assert.deepEqual(result.exit.empty, []);
  assert.equal(result.calls.run.length, 0);
  assert.equal(result.calls.readonly.length, 0, 'preflight failure leaves posture untouched');
  assert.equal(result.calls.shell.length, 1);
});

test('fails fast before any model run when groups exist but have no members', () => {
  const result = run(PR, { env: modelGroupsEnv({ project: { 'code-review': 0, plan: 0 }, missingGlobal: true }).env });
  assert.equal(result.exit.reason, 'needs-input');
  assert.deepEqual(result.exit.missing, []);
  assert.deepEqual(result.exit.empty, ['code-review', 'plan']);
  assert.equal(result.calls.run.length, 0);
});

test('fails fast when the project groups config is invalid JSON', () => {
  const result = run(PR, { env: modelGroupsEnv({ project: { 'code-review': 1, plan: 1 }, corrupt: true, missingGlobal: true }).env });
  assert.equal(result.exit.reason, 'needs-input');
  assert.match(result.exit.diagnostic, /not usable/);
  assert.equal(result.calls.run.length, 0);
});

test('passes the preflight when project defines both groups with members and global is absent', () => {
  const result = run();
  assert.equal(result.exit.reason, 'ok');
  assert.equal(result.calls.shell.length, 1);
  assert.equal(result.calls.run.length, 2);
});

test('global-scoped groups satisfy the preflight when project config is absent', () => {
  const result = run(PR, { env: modelGroupsEnv({ project: null, global: { 'code-review': 1, plan: 1 } }).env });
  assert.equal(result.exit.reason, 'ok');
  assert.equal(result.calls.run.length, 2);
});

test('schema keeps intent, observed changes, evidence and missing sources separate', () => {
  const schema = run().calls.run[0].options.output.schema;
  assert.equal(schema.additionalProperties, false);
  for (const field of ['summary', 'base_sha', 'head_sha', 'coverage', 'sources', 'domains', 'limitations']) {
    assert.ok(schema.required.includes(field), field);
  }
  assert.deepEqual(schema.properties.coverage.enum, ['complete', 'partial', 'blocked']);
  const source = schema.properties.sources.items;
  assert.deepEqual(source.properties.status.enum, ['read', 'unavailable']);
  const domain = schema.properties.domains.items;
  for (const field of ['name', 'intent', 'changes', 'files', 'issues', 'evidence']) {
    assert.ok(domain.required.includes(field), field);
  }
});

test('runs explicit skills with nonempty args so fenced input does not corrupt skill expansion', () => {
  const calls = run().calls.run;
  assert.deepEqual(calls.map(call => call.prompt), ['/skill:review-understanding-summary', '/skill:review-understanding-splits']);
  for (const call of calls) {
    assert.equal(call.options.args, PR, 'a literal space separates the skill name from args and fenced input');
    assert.equal(call.options.model, undefined, 'frontmatter controls model selection');
    assert.equal(call.options.thinking, undefined, 'no workflow override of group thinking');
  }
  const source = readFileSync(WORKFLOW, 'utf8');
  assert.doesNotMatch(source, /const (understandPrompt|splitPrompt)|gh pr view/, 'task instructions live only in skills');
});

test('discoverable package skills bind their model groups and readonly policy', () => {
  const expected = [['review-understanding-summary', 'code-review'], ['review-understanding-splits', 'plan']];
  assert.deepEqual(SKILLS.sort(), expected.map(([name]) => name).sort());
  for (const [name, group] of expected) {
    const text = skillText(name);
    const frontmatter = text.match(/^---\n([\s\S]*?)\n---\n/);
    assert.ok(frontmatter, `${name}: YAML frontmatter`);
    assert.match(frontmatter[1], new RegExp(`^name: ${name}$`, 'm'));
    assert.match(frontmatter[1], /^description: .+$/m);
    assert.match(frontmatter[1], new RegExp(`^model-group: ${group}$`, 'm'));
    assert.match(frontmatter[1], /^readonly: true$/m, 'must be a YAML boolean, not a quoted string');
    assert.doesNotMatch(frontmatter[1], /^model:/m, 'no explicit model overrides the group');
  }
});

test('skill bodies preserve PR/issue/diff research and evidence-bound split suggestions', () => {
  const first = skillText('review-understanding-summary');
  const second = skillText('review-understanding-splits');
  for (const phrase of ['gh pr view', 'gh pr diff', 'gh issue view', 'closingIssuesReferences', 'mentioned', 'full diff', 'untrusted data', 'Do not post', 'Do not spawn', 'base_sha', 'head_sha', 'truncated']) {
    assert.ok(first.includes(phrase), phrase);
  }
  for (const phrase of ['domain', 'ticket', 'dependencies', 'tests', 'independently mergeable', 'cohesive', 'Do not browse', 'untrusted data']) {
    assert.ok(second.includes(phrase), phrase);
  }
});

for (const args of ['', 'not-a-url', 'https://github.com/example/project/issues/42', 'https://other.test/example/project/pull/42', `${PR} --unknown`, `${PR} --plain extra`, `${PR};echo bad`]) {
  test(`invalid input does not start model work: ${JSON.stringify(args)}`, () => {
    const result = run(args);
    assert.equal(result.error, null);
    assert.equal(result.exit.reason, 'needs-input');
    assert.equal(result.calls.run.length, 0);
    assert.equal(result.calls.readonly.length, 0);
  });
}

test('normalizes a trailing slash and surrounding whitespace', () => {
  const result = run(`  ${PR}/  \n`);
  assert.equal(result.error, null);
  assert.equal(result.exit.pr_url, PR);
});

for (const initiallyReadonly of [false, true]) {
  test(`restores the original readonly posture (${initiallyReadonly}) on success and either run failing`, () => {
    const initialState = { readonly: initiallyReadonly };
    assert.deepEqual(run(PR, { initialState }).calls.readonly, [true, initiallyReadonly]);
    for (const failAt of [1, 2]) {
      const result = run(PR, { initialState, runStub: (_prompt, _options, { calls }) => {
        if (calls.run.length === failAt) throw new Error('Synthetic model failure');
        return { output: understanding };
      } });
      assert.match(result.error.message, /Synthetic model failure/);
      assert.equal(result.calls.run.length, failAt, 'no retry or fallback');
      assert.deepEqual(result.calls.readonly, [true, initiallyReadonly]);
      assert.equal(result.exit, null, 'model failure is not success');
    }
  });
}

test('partial research is forwarded without silently becoming complete evidence', () => {
  const partial = { ...understanding, coverage: 'partial', limitations: ['Issue #7 was inaccessible.'] };
  const result = run(PR, { runStub: (_prompt, _options, { calls }) => calls.run.length === 1 ? { output: partial } : { text: 'Tentative review order only.' } });
  assert.equal(result.error, null);
  assert.deepEqual(result.calls.run[1].options.input.understanding, partial);
  assert.equal(result.exit.understanding.coverage, 'partial');
});
