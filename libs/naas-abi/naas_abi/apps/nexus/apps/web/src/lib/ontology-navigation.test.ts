import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  browserRoute, dictionaryFilterRoute, lastOntologyRoute, normalizeOntologyRoute,
  ontologyBrowser, rememberOntologyRoute, termRoute, viewRoute,
  dictionaryFilters, dictionaryFiltersRoute, systemRoute,
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

test('type checkboxes support legacy links, multiple choices, duplicates and all types', () => {
  assert.deepEqual(dictionaryFilters('view=attributes'), ['attribute']);
  assert.deepEqual(dictionaryFilters('view=system&termFilter=attribute'), ['attribute']);
  assert.deepEqual(dictionaryFilters('termFilter=entity&termFilter=attribute&termFilter=entity&termFilter=invalid'), ['entity','attribute']);
  assert.deepEqual(dictionaryFilters('view=classes&termFilter=all'), []);
  assert.deepEqual(dictionaryFilters('termFilter=all&termFilter=entity'), []);
});

test('checking a second type retains a compatible selection and all other filters', () => {
  const current='view=classes&term=c&termType=entity&termFilter=entity&dictionaryFile=a&dictionaryFile=b&systemFilter=one&systemFilter=two&spacing=compact&connectors=orthogonal';
  const next=dictionaryFiltersRoute(current,['entity','attribute']);
  assert.deepEqual(next.getAll('termFilter'), ['entity','attribute']);
  assert.equal(next.get('term'),'c');
  assert.equal(next.get('view'),'classes');
  assert.deepEqual(next.getAll('dictionaryFile'),['a','b']);
  assert.deepEqual(next.getAll('systemFilter'),['one','two']);
  assert.equal(next.get('spacing'),'compact');
  assert.equal(next.get('connectors'),'orthogonal');
  const removed=dictionaryFiltersRoute(next.toString(),['attribute']);
  assert.equal(removed.has('term'),false);
  assert.equal(removed.has('termType'),false);
  assert.equal(removed.get('view'),'attributes');
  const all=dictionaryFiltersRoute(removed.toString(),[]);
  assert.equal(all.get('termFilter'),'all');
  assert.deepEqual(dictionaryFilters(all.toString()),[]);
});

test('accumulated types survive term selection, canvas switches and system overview', () => {
  let route=dictionaryFiltersRoute('browser=dictionary&view=overview', ['entity','attribute']);
  route=termRoute(route.toString(),{id:'a',type:'attribute'});
  route=viewRoute(route.toString(),'network');
  route=viewRoute(route.toString(),'details');
  assert.equal(route.get('view'),'attributes');
  assert.equal(route.get('term'),'a');
  assert.deepEqual(route.getAll('termFilter'),['entity','attribute']);
  route=systemRoute(route.toString());
  assert.deepEqual(route.getAll('termFilter'),['entity','attribute']);
  route=viewRoute(route.toString(),'overview');
  assert.deepEqual(route.getAll('termFilter'),['entity','attribute']);
  route=termRoute(route.toString(),{id:'p',type:'relationship'});
  assert.deepEqual(route.getAll('termFilter'),['entity','attribute','relationship']);
  assert.equal(route.get('view'),'relations');
});
