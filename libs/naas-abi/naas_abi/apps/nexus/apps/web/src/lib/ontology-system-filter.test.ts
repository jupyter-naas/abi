import test from 'node:test';
import assert from 'node:assert/strict';
import { filterSystems, selectedSystems, systemFilterRoute, systemOntologyPaths } from './ontology-system-filter';
import { buildOntologySystems } from './ontology-system-graph';
import type { DictionaryTerm } from './ontology-dictionary-tree';
import { buildOntologyDashboard, dashboardTerms, dashboardCoverage } from './ontology-dashboard';
import { systemRoute, termRoute } from './ontology-navigation';

const systems = buildOntologySystems(['alpha', 'beta', 'gamma'].map(id => ({
  id, name: id, type: 'entity', systemViewKind: 'system',
})));

test('system checkboxes accumulate and never add systems outside the visible catalog', () => {
  assert.equal(filterSystems(systems, '').length, 3);
  assert.deepEqual(filterSystems(systems, 'systemFilter=beta&systemFilter=alpha&systemFilter=private').map(s => s.term.id), ['alpha', 'beta']);
  assert.deepEqual(selectedSystems('systemFilter=beta&systemFilter=beta&systemFilter='), ['beta']);
  assert.equal(filterSystems(systems, 'systemFilter=private').length, 0);
});

test('checkbox changes clear stale drill-down and preserve other sidebar filters', () => {
  const current = 'view=system&system=gamma&subsystem=s1&process=p1&processView=ontology&term=x&termType=entity&termFilter=entity&dictionaryFile=a&dictionaryFile=b';
  const next = systemFilterRoute(current, ['alpha', 'beta']);
  assert.deepEqual(next.getAll('systemFilter'), ['alpha', 'beta']);
  assert.deepEqual(next.getAll('dictionaryFile'), ['a', 'b']);
  for (const key of ['system', 'subsystem', 'process', 'term', 'termType', 'processView']) assert.equal(next.get(key), null);
  assert.equal(next.get('termFilter'), 'entity');
  const drill = systemRoute(next.toString(), 'beta', undefined, 'engage');
  assert.deepEqual(drill.getAll('systemFilter'), ['alpha', 'beta']);
  assert.deepEqual(systemRoute(drill.toString()).getAll('systemFilter'), ['alpha', 'beta']);
  assert.deepEqual(termRoute(drill.toString(), {id: 'person', type: 'entity'}).getAll('systemFilter'), ['alpha', 'beta']);
  assert.deepEqual(selectedSystems(systemFilterRoute(next.toString(), []).toString()), []);
});

const source = (path: string) => ({ path, name: path, moduleName: 'module' });
const scopedCatalog: DictionaryTerm[] = [
  { id: 'alpha', name: 'Alpha', type: 'entity', systemViewKind: 'system', sources: [source('alpha.ttl')] },
  { id: 'beta', name: 'Beta', type: 'entity', systemViewKind: 'system', sources: [source('beta.ttl')] },
  { id: 'group', name: 'Group', type: 'entity', systemViewKind: 'subsystem', systemViewParents: [{id: 'alpha', name: 'Alpha'}], parents: [{id: 'http://purl.obolibrary.org/obo/BFO_0000015', name: 'Process'}], sources: [source('alpha.ttl')] },
  { id: 'process', name: 'Process', type: 'entity', parents: [{id: 'group', name: 'Group'}], sources: [source('process.ttl')] },
  { id: 'participant', name: 'Participant', type: 'entity', sources: [source('process.ttl')] },
  { id: 'shared', name: 'Shared', type: 'entity', sources: [source('alpha.ttl'), source('beta.ttl')], metadata: {label: ['alpha.ttl'], definition: ['beta.ttl'], example: []} },
  { id: 'shared', name: 'Shared individual', type: 'individual', sources: [source('beta.ttl')] },
  { id: 'alpha:unrelated', name: 'Unrelated', type: 'entity', sources: [source('other.ttl')] },
];

test('system file scope includes declared processes, accumulates systems and fails closed on stale selections', () => {
  assert.equal(systemOntologyPaths(scopedCatalog, ''), null);
  assert.deepEqual([...systemOntologyPaths(scopedCatalog, 'systemFilter=alpha')!].sort(), ['alpha.ttl', 'process.ttl']);
  assert.deepEqual([...systemOntologyPaths(scopedCatalog, 'systemFilter=alpha&systemFilter=beta&systemFilter=private')!].sort(), ['alpha.ttl', 'beta.ttl', 'process.ttl']);
  assert.equal(systemOntologyPaths(scopedCatalog, 'systemFilter=private')!.size, 0);
  assert.equal(systemOntologyPaths([], 'systemFilter=alpha')!.size, 0);
});

test('dashboard and dictionary use the same system/file intersection without inflating shared metadata', () => {
  const before = JSON.stringify(scopedCatalog);
  const paths = systemOntologyPaths(scopedCatalog, 'systemFilter=alpha')!;
  const inventory = ['alpha.ttl', 'beta.ttl', 'process.ttl', 'other.ttl'].map(source);
  for (const files of [[], ['process.ttl'], ['beta.ttl'], ['private.ttl']]) {
    const tiles = buildOntologyDashboard(inventory, scopedCatalog, []).filter(tile => paths.has(tile.path) && (!files.length || files.includes(tile.path)));
    const dictionary = scopedCatalog.filter(term => term.sources?.some(item => paths.has(item.path) && (!files.length || files.includes(item.path))));
    const key = (term: DictionaryTerm) => `${term.type}:${term.id}`;
    assert.deepEqual(dashboardTerms(tiles).map(key).sort(), dictionary.map(key).sort());
  }
  const shared = scopedCatalog.filter(term => term.id === 'shared' && term.type === 'entity');
  const coverage = dashboardCoverage(shared, [...paths]);
  assert.equal(coverage.total, 1);
  assert.equal(coverage.metrics.find(metric => metric.key === 'definition')!.present, 0);
  assert.equal(JSON.stringify(scopedCatalog), before);
});
