import assert from 'node:assert/strict';
import { test } from 'node:test';
import { iconTarget, iconTargetKey, pickerPosition, searchIconNames, validIconPaths } from './ontology-icon-library';

test('search accepts multiple words and hyphens without depending on remote search', () => {
  assert.deepEqual(searchIconNames(['school-outline', 'school-rounded', 'public'], 'SCHOOL outline'), ['school-outline']);
  assert.deepEqual(searchIconNames(['school-outline'], 'school-outline'), ['school-outline']);
  assert.deepEqual(searchIconNames(['public'], 'unknown'), []);
});

test('object identity uses IRI and kind, not its editable label or source order', () => {
  const a = iconTarget({ name: 'Original', id: 'urn:x', type: 'entity' })!;
  const b = iconTarget({ name: 'Renamed', id: 'urn:x', type: 'entity' })!;
  assert.equal(iconTargetKey(a), iconTargetKey(b));
  assert.notEqual(iconTargetKey(a), iconTargetKey({ kind: 'annotation', resource_id: 'urn:x' }));
  assert.deepEqual(iconTarget({ name: 'Ontology', path: '/workspace/a.ttl' }), { kind: 'file', resource_id: '/workspace/a.ttl' });
  assert.equal(iconTarget({ name: 'Unresolved node' }), null);
});

test('picker fits near the right and bottom edges and on narrow screens', () => {
  for (const width of [320, 1440]) {
    const position = pickerPosition({ left: width - 40, bottom: 690 }, { width, height: 700 });
    assert.ok(position.left >= 12);
    assert.ok(position.left + position.width <= width - 12);
    assert.ok(position.top + position.maxHeight <= 688);
  }
});

test('only SVG path coordinates may enter the renderer', () => {
  assert.ok(validIconPaths(['M0 1h2v3z']));
  for (const input of [[], ['<svg onload="alert(1)">'], ['javascript:alert(1)'], { path: 'M0 1' }, ['M'.repeat(60001)]]) assert.equal(validIconPaths(input), false);
});
