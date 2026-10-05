import { test } from 'node:test';
import assert from 'node:assert/strict';
import { classRestrictions } from './ontology-class-properties';
import type { DictionaryTerm } from './ontology-dictionary-tree';

const file = { path: 'people/PeopleOntology.ttl', name: 'People', moduleName: 'people' };
const restriction = (property: string, constraint: string, target: string) =>
  ({ property: { id: `abi:${property}`, name: property }, kind: 'restriction' as const, constraint, target: { id: `abi:${target}`, name: target }, sources: [file] });

test('lists the class restrictions first, then those inherited from its parents', () => {
  const act: DictionaryTerm = { id: 'abi:Act', name: 'Act', type: 'entity', relations: [restriction('hasParticipant', 'some', 'Agent')] };
  const work: DictionaryTerm = { id: 'abi:ActOfWorking', name: 'Act of Working', type: 'entity', parents: [{ id: act.id, name: act.name }],
    relations: [restriction('occursIn', 'some', 'GeospatialRegion'), { ...restriction('hasParticipant', 'some', 'Person'), kind: 'assertion' }] };
  const rows = classRestrictions(work, [act, work]);
  assert.deepEqual(rows.map(row => [row.declaredOn.name, row.property.name, row.constraint, row.target.name]), [
    ['Act of Working', 'occursIn', 'some', 'GeospatialRegion'],
    ['Act', 'hasParticipant', 'some', 'Agent'],
  ]);
});
