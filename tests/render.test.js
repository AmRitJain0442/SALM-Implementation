// Run with:  node --test tests/
// Also invoked from the Python suite via tests/test_web.py.
const test = require('node:test');
const assert = require('node:assert');
const { markUp, escapeHtml } = require('../web/render.js');

const plain = (text) => ({ text, corrections: [], expansions: [] });

test('leaves ordinary text alone', () => {
  assert.strictEqual(markUp(plain('nothing to mark here')), 'nothing to mark here');
});

test('escapes markup in the transcript', () => {
  assert.strictEqual(markUp(plain('a < b & c')), 'a &lt; b &amp; c');
});

test('marks a repaired term and shows what was heard', () => {
  const html = markUp({
    text: 'feeds Halberd daily',
    corrections: [{ heard: 'Halbert', canonical: 'Halberd' }],
    expansions: [],
  });

  assert.strictEqual(
    html,
    'feeds <span class="fix">Halberd</span><span class="was">Halbert</span> daily'
  );
});

test('marks an expanded acronym', () => {
  const html = markUp({
    text: 'ARR (Annual Recurring Revenue) rose',
    corrections: [],
    expansions: [{ canonical: 'ARR', expansion: 'Annual Recurring Revenue' }],
  });

  assert.strictEqual(
    html,
    '<span class="exp">ARR (Annual Recurring Revenue)</span> rose'
  );
});

test('nests a repair inside an expansion when a term is both', () => {
  const html = markUp({
    text: 'CRIMS (Client Risk Management System) flagged it',
    corrections: [{ heard: 'Crims', canonical: 'CRIMS' }],
    expansions: [{ canonical: 'CRIMS', expansion: 'Client Risk Management System' }],
  });

  assert.strictEqual(
    html,
    '<span class="exp"><span class="fix">CRIMS</span><span class="was">Crims</span>' +
      ' (Client Risk Management System)</span> flagged it'
  );
});

test('a glossary term matching a css class name cannot corrupt the markup', () => {
  // A lowercase term like "fix" is plausible (FIX protocol) and would rewrite
  // class attributes if marking were done by replacing on escaped HTML.
  const html = markUp({
    text: 'the fix landed',
    corrections: [{ heard: 'fics', canonical: 'fix' }],
    expansions: [],
  });

  assert.strictEqual(
    html,
    'the <span class="fix">fix</span><span class="was">fics</span> landed'
  );
});

test('escapes a heard form containing markup', () => {
  const html = markUp({
    text: 'Orbex runs',
    corrections: [{ heard: '<b>Orbeck</b>', canonical: 'Orbex' }],
    expansions: [],
  });

  assert.ok(html.includes('&lt;b&gt;Orbeck&lt;/b&gt;'));
  assert.ok(!html.includes('<b>'));
});

test('handles two repairs in one utterance', () => {
  const html = markUp({
    text: 'Orbex feeds Halberd',
    corrections: [
      { heard: 'Orbeck', canonical: 'Orbex' },
      { heard: 'Halbert', canonical: 'Halberd' },
    ],
    expansions: [],
  });

  assert.ok(html.startsWith('<span class="fix">Orbex</span>'));
  assert.ok(html.includes('<span class="fix">Halberd</span>'));
});

test('escapeHtml quotes attribute-breaking characters', () => {
  assert.strictEqual(escapeHtml('a"b'), 'a&quot;b');
});
