import test from 'node:test';
import assert from 'node:assert/strict';
import { filterSystems, selectedSystems, systemFilterRoute } from './ontology-system-filter';
import { buildOntologySystems } from './ontology-system-graph';
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
