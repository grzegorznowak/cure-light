// Review-understanding package entry. Canonical source under workflows/review-understanding/;
// discovery entries are symlinks into this package (see install.mjs).
// Two skill runs: understand a PR, then suggest digestible splits.
return defineWorkflow((workflow) => {
  const [url, flag, ...extra] = load('args').trim().split(/\s+/);
  if (!/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/pull\/[1-9]\d*\/?$/.test(url || '') ||
      (flag !== undefined && flag !== '--plain') || extra.length) {
    return workflow.exit({ reason: 'needs-input', usage: 'review-understanding <https://github.com/OWNER/REPO/pull/N> [--plain]' });
  }
  const prUrl = url.replace(/\/$/, '');
  const format = flag === '--plain' ? 'plain' : 'structured';

  // Model-group preflight: the two skills route through `model-group:` frontmatter.
  // Fail before any model spend when either required group is absent or has no members.
  const groupsScript = String.raw`const fs = require('node:fs'), path = require('node:path');
const REQUIRED = ['code-review', 'plan'];
const project = process.env.REVIEW_UNDERSTANDING_PROJECT_GROUPS || path.join(process.cwd(), '.pi', 'pi-schematic', 'model-groups.json');
const global = process.env.REVIEW_UNDERSTANDING_GLOBAL_GROUPS || path.join(process.env.HOME || '', '.pi', 'agent', 'pi-schematic', 'model-groups.json');
const scopes = { project, global };
const checked = [];
let error = null;
const groups = {};
for (const file of [project, global]) {
  let info = null;
  try { info = fs.statSync(file); } catch (e) { if (e.code !== 'ENOENT') { error = 'stat failed: ' + file + ': ' + e.message; break; } }
  if (!info) continue;
  if (!info.isFile()) { error = 'not a regular file: ' + file; break; }
  checked.push(file);
  let parsed;
  try { parsed = JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch (e) { error = 'invalid JSON in ' + file + ': ' + e.message; break; }
  const g = parsed && parsed.groups;
  if (!g || typeof g !== 'object' || Array.isArray(g)) { error = 'no groups object in ' + file; break; }
  for (const name of Object.keys(g)) {
    const def = g[name];
    const valid = def && typeof def === 'object' && Array.isArray(def.models);
    groups[name] = groups[name] || { present: false, hasMember: false };
    groups[name].present = true;
    if (valid && def.models.length > 0) groups[name].hasMember = true;
  }
}
const missing = [], empty = [];
for (const name of REQUIRED) {
  if (!groups[name] || !groups[name].present) missing.push(name);
  else if (!groups[name].hasMember) empty.push(name);
}
console.log(JSON.stringify({ ok: missing.length === 0 && empty.length === 0 && !error, required: REQUIRED, missing, empty, checked, error }));`;
  const quote = (value) => "'" + String(value).replace(/'/g, "'\\''") + "'";
  const groupsCheck = workflow.shell('node -e ' + quote(groupsScript));
  if (!groupsCheck.ok) {
    return workflow.exit({ reason: 'needs-input', diagnostic: 'Model-group preflight could not run.', detail: groupsCheck.output.slice(0, 400) });
  }
  let groupsReport;
  try { groupsReport = JSON.parse(groupsCheck.output); } catch { groupsReport = null; }
  if (!groupsReport || typeof groupsReport !== 'object' || groupsReport.ok !== true) {
    return workflow.exit({
      reason: 'needs-input',
      diagnostic: 'Required model groups are not usable.',
      missing: groupsReport && groupsReport.missing ? groupsReport.missing : ['code-review', 'plan'],
      empty: groupsReport && groupsReport.empty ? groupsReport.empty : [],
      hint: 'Define code-review and plan groups with at least one model each in .pi/pi-schematic/model-groups.json (or your agent global config). See README "Model-group routing".',
    });
  }

  const strings = { type: 'array', items: { type: 'string' } };
  const schema = {
    type: 'object', additionalProperties: false,
    required: ['summary', 'base_sha', 'head_sha', 'coverage', 'sources', 'domains', 'limitations'],
    properties: {
      summary: { type: 'string' }, base_sha: { type: 'string' }, head_sha: { type: 'string' },
      coverage: { type: 'string', enum: ['complete', 'partial', 'blocked'] },
      sources: {
        type: 'array', items: {
          type: 'object', additionalProperties: false, required: ['url', 'kind', 'status', 'note'],
          properties: {
            url: { type: 'string' }, kind: { type: 'string', enum: ['pr', 'issue', 'diff'] },
            status: { type: 'string', enum: ['read', 'unavailable'] }, note: { type: 'string' },
          },
        },
      },
      domains: {
        type: 'array', items: {
          type: 'object', additionalProperties: false,
          required: ['name', 'intent', 'changes', 'files', 'issues', 'evidence'],
          properties: {
            name: { type: 'string' }, intent: { type: 'string' }, changes: strings,
            files: strings, issues: strings, evidence: strings,
          },
        },
      },
      limitations: strings,
    },
  };
  workflow.checkpoint({ phase: 'ready', pr_url: prUrl, format });
  const previousReadonly = workflow.state().readonly;
  // Keep the guard for hosts that do not apply skill frontmatter.
  workflow.readonly(true);
  let understanding;
  let splits;
  try {
    // Nonempty args keep the skill name separate from the appended input block.
    const options = { args: prUrl, input: { pr_url: prUrl } };
    if (format === 'structured') options.output = { schema };
    const first = workflow.run('/skill:review-understanding-summary', options);
    understanding = format === 'structured' ? first.output : first.text;
    workflow.checkpoint({ phase: 'understood', pr_url: prUrl, format, understanding });
    const second = workflow.run('/skill:review-understanding-splits', { args: prUrl, input: { pr_url: prUrl, format, understanding } });
    splits = second.text;
    workflow.checkpoint({ phase: 'split', pr_url: prUrl, format, understanding, splits });
  } finally {
    workflow.readonly(previousReadonly);
  }
  return workflow.exit({ reason: 'ok', pr_url: prUrl, format, understanding, splits });
});
