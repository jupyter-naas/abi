import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  browserRoute, dictionaryFilterRoute, lastOntologyRoute, normalizeOntologyRoute,
  ontologyBrowser, rememberOntologyRoute, termRoute, viewRoute,
} from './ontology-navigation';

test('first visit opens the dashboard with the dictionary and no invented file scope', () => {
  assert.equal(ontologyBrowser(''), 'dictionary');
  const route = lastOntologyRoute('new-workspace');
  assert.equal(route.get('browser'), 'dictionary');
  assert.equal(route.get('view'), 'overview');
  assert.equal(route.has('ontology'), false);
});

test('legacy Network links no longer bring back the Files sidebar', () => {
  const route = normalizeOntologyRoute('view=network&ontology=%2Fallowed%2Fterms.ttl');
  assert.equal(route.get('browser'), 'dictionary');
  assert.equal(route.get('view'), 'network');
  assert.equal(route.get('ontology'), '/allowed/terms.ttl');
});

test('an explicit Files selection survives normalization', () => {
  const route = normalizeOntologyRoute('browser=files&ontology=%2Fallowed%2Fterms.ttl');
  assert.equal(route.get('browser'), 'files');
  assert.equal(route.get('view'), 'network');
});

test('leaving and reopening restores the full route for the correct workspace', () => {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    sessionStorage: { getItem: (key: string) => values.get(key) || null, setItem: (key: string, value: string) => values.set(key, value) },
  } });
  try {
    const selection = new URLSearchParams({ browser: 'dictionary', view: 'annotations', termFilter: 'annotation', term: 'https://example.org/label', termType: 'annotation' });
    selection.append('dictionaryFile', '/allowed/one file.ttl');
    selection.append('dictionaryFile', '/allowed/two.ttl');
    rememberOntologyRoute('workspace-a', selection.toString());
    assert.equal(lastOntologyRoute('workspace-a').toString(), selection.toString());
    assert.equal(lastOntologyRoute('workspace-b').has('term'), false);
    assert.deepEqual(lastOntologyRoute('workspace-b').getAll('dictionaryFile'), []);
    rememberOntologyRoute('workspace-b', 'browser=files&ontology=%2Fother.ttl&view=network');
    assert.equal(lastOntologyRoute('workspace-b').get('browser'), 'files');
    assert.equal(lastOntologyRoute('workspace-a').toString(), selection.toString());
  } finally { Reflect.deleteProperty(globalThis, 'window'); }
});

test('checkbox selections survive type, canvas, term and sidebar navigation', () => {
  let route = normalizeOntologyRoute('dictionaryFile=%2Fa.ttl&dictionaryFile=%2Fb.ttl');
  route = dictionaryFilterRoute(route.toString(), 'annotation');
  route = termRoute(route.toString(), { id: 'https://example.org/label', type: 'annotation' });
  route = viewRoute(route.toString(), 'network');
  route = viewRoute(route.toString(), 'details');
  route = browserRoute(route.toString(), 'files');
  route = browserRoute(route.toString(), 'dictionary');
  assert.deepEqual(route.getAll('dictionaryFile'), ['/a.ttl', '/b.ttl']);
  assert.equal(route.get('view'), 'annotations');
  assert.equal(route.get('term'), 'https://example.org/label');
  assert.equal(route.get('termFilter'), 'annotation');
});

test('blocked browser storage cannot break navigation', () => {
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    get sessionStorage() { throw new Error('Storage disabled'); },
  } });
  try {
    assert.doesNotThrow(() => rememberOntologyRoute('workspace-a', 'browser=files'));
    assert.equal(lastOntologyRoute('workspace-a').get('browser'), 'dictionary');
  } finally { Reflect.deleteProperty(globalThis, 'window'); }
});
