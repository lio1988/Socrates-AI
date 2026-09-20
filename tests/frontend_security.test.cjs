const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const { join } = require('node:path');

const source = readFileSync(join(__dirname, '..', 'frontend.html'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = new Map();
function node() {
  return { textContent: '', innerHTML: '', style: {}, appendChild() {}, querySelector() { return node(); } };
}
const context = vm.createContext({
  window: { location: { origin: 'http://localhost:8000' } },
  document: {
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, node());
      return nodes.get(id);
    },
    createElement: node,
  },
});
vm.runInContext(script, context);
const attack = '<img src=x onerror="alert(1)">';

test('untrusted replay values and turn metadata are escaped', () => {
  const rendered = [
    context.metric(attack, attack),
    context.renderAuditChecks({ [attack]: true }),
    context.renderClaimTimeline([{ state: attack, confidence: attack, text: attack }]),
    context.renderTurn({ model_id: attack, round: attack, content: attack }).innerHTML,
  ];
  for (const html of rendered) {
    assert.ok(!html.includes('<img'));
    assert.ok(html.includes('&lt;img'));
  }
  assert.ok(context.metric('count', 0).includes('>0<'));
});

test('violations are text and score fields cannot inject markup', () => {
  context.render({ status: 'running', topic: attack, scores: { [attack]: attack }, constitution_violations: [attack], history: [] });
  assert.equal(nodes.get('violations').textContent, '⚠️ ' + attack);
  assert.equal(nodes.get('violations').innerHTML, '');
  assert.ok(!nodes.get('scores').innerHTML.includes('<img'));
});
