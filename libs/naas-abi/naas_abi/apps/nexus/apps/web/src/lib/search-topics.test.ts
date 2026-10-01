import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  formatPeriod, initials, readSearchRoute, resolveScope, safeImage, searchHref,
} from './search-topics';

test('a search view round-trips through its URL', () => {
  const href = searchHref('ws 1', { scope: 'person', q: 'alice', item: 'http://x/a#b', tab: 'ontology' });
  assert.equal(href.split('?')[0], '/workspace/ws%201/search');
  assert.deepEqual(readSearchRoute(new URLSearchParams(href.split('?')[1])), {
    scope: 'person', q: 'alice', item: 'http://x/a#b', tab: 'ontology',
  });
  assert.equal(searchHref('w', {}), '/workspace/w/search');
  assert.equal(searchHref('w', { scope: 'all', q: 'x' }), '/workspace/w/search?q=x');
});

test('the earlier ?topic= links still open their topic', () => {
  assert.equal(readSearchRoute(new URLSearchParams('topic=person')).scope, 'person');
});

test('an unknown scope falls back to the All view', () => {
  const scopes = [{ id: 'person' }, { id: 'files' }];
  assert.equal(resolveScope(scopes, 'files'), 'files');
  assert.equal(resolveScope(scopes, 'nope'), null);
  assert.equal(resolveScope(scopes, null), null);
});

test('only loadable images are rendered', () => {
  assert.equal(safeImage('https://cdn/x.png'), 'https://cdn/x.png');
  assert.equal(safeImage('assets/portraits/a.svg'), null);
  assert.equal(safeImage('javascript:alert(1)'), null);
  assert.equal(safeImage(null), null);
});

test('periods and initials', () => {
  assert.equal(formatPeriod('2019-10-01', null), 'Oct 2019 – present');
  assert.equal(formatPeriod('2019-10-01', '2022-12-31'), 'Oct 2019 – Dec 2022');
  assert.equal(formatPeriod(null, null), null);
  assert.equal(initials('Alice  Dupont'), 'AD');
  assert.equal(initials(''), '?');
});
