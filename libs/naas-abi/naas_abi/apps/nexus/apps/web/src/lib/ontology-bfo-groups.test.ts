import { test } from 'node:test';
import assert from 'node:assert/strict';
import { groupClassesByBfoBucket } from './ontology-bfo-groups';
import type { DictionaryTerm } from './ontology-dictionary-tree';

const BFO = 'http://purl.obolibrary.org/obo/';
const quality: DictionaryTerm = { id: `${BFO}BFO_0000019`, name: 'quality', type: 'entity' };
const skill: DictionaryTerm = { id: 'people:Skill', name: 'Skill', type: 'entity', parents: [quality] };
// Parent chain is outside the dictionary (CCO); only the server bucket classifies it.
const work: DictionaryTerm = { id: 'people:ActOfWorking', name: 'Act of Working', type: 'entity',
  parents: [{ id: 'cco:ont00000228', name: 'Planned Act' }], bfoBucket: `${BFO}BFO_0000015` };
const person: DictionaryTerm = { id: 'abi:Person', name: 'Person', type: 'entity', bfoBucket: `${BFO}BFO_0000040` };
const orphan: DictionaryTerm = { id: 'x:Orphan', name: 'Orphan', type: 'entity', parents: [{ id: 'cco:ont00000001', name: 'Elsewhere' }] };
const property: DictionaryTerm = { id: 'people:hasSkill', name: 'has skill', type: 'relationship' };

const entity: DictionaryTerm = { id: `${BFO}BFO_0000001`, name: 'entity', type: 'entity' };
const thing: DictionaryTerm = { id: 'x:Thing', name: 'Thing', type: 'entity', parents: [entity] };
const serverEntity: DictionaryTerm = { id: 'x:Vague', name: 'Vague', type: 'entity', bfoBucket: `${BFO}BFO_0000001` };

test('returns every bucket in display order, Entity and Unknown included, properties excluded', () => {
  const all = [quality, skill, work, person, orphan, property, entity, thing, serverEntity];
  const groups = groupClassesByBfoBucket([skill, work, person, orphan, property, thing, serverEntity], all);
  assert.deepEqual(groups.map(group => group.bucket.type), [
    'Process', 'Temporal Region', 'Material Entity', 'Site', 'GDC', 'Quality', 'Realizable', 'Entity', 'Unknown',
  ]);
  const names = Object.fromEntries(groups.map(group => [group.bucket.type, group.terms.map(term => term.name)]));
  assert.deepEqual(names['Material Entity'], ['Person']);
  assert.deepEqual(names.Process, ['Act of Working']);
  assert.deepEqual(names.Quality, ['Skill']);
  assert.deepEqual(names.Entity, ['Thing', 'Vague']);
  assert.deepEqual(names.Unknown, ['Orphan']);
  assert.deepEqual(names.Site, []);
});

test('a specific bucket on another branch wins over entity', () => {
  const both: DictionaryTerm = { id: 'x:Both', name: 'Both', type: 'entity', parents: [entity, quality] };
  const groups = groupClassesByBfoBucket([both], [both, entity, quality]);
  assert.deepEqual(groups.find(group => group.bucket.type === 'Quality')?.terms.map(term => term.name), ['Both']);
});

test('a class reaches its bucket through a parent outside the selection', () => {
  const sub: DictionaryTerm = { id: 'x:Sub', name: 'Sub', type: 'entity', parents: [{ id: 'abi:Person', name: 'Person' }] };
  const groups = groupClassesByBfoBucket([sub], [sub, person]);
  assert.deepEqual(groups.filter(group => group.terms.length).map(group => group.bucket.type), ['Material Entity']);
});

test('each bucket nests its classes under parents from the same bucket only', () => {
  const material: DictionaryTerm = { id: 'abi:MaterialEntity', name: 'material entity', type: 'entity', bfoBucket: `${BFO}BFO_0000040` };
  const agent: DictionaryTerm = { id: 'abi:Agent', name: 'Agent', type: 'entity', parents: [material], bfoBucket: `${BFO}BFO_0000040` };
  const org: DictionaryTerm = { id: 'abi:Organization', name: 'Organization', type: 'entity',
    parents: [{ id: 'cco:ont00000300', name: 'Group of Agents' }], bfoBucket: `${BFO}BFO_0000040` };
  const pers: DictionaryTerm = { ...person, parents: [{ id: 'cco:ont00000562', name: 'Animal' }] };
  const all = [material, agent, org, pers];
  const group = groupClassesByBfoBucket(all, all).find(item => item.bucket.type === 'Material Entity')!;
  const shape = (nodes: typeof group.tree): unknown => nodes.map(node => [node.name, shape(node.children)]);
  assert.deepEqual(shape(group.tree), [
    ['material entity', [['Agent', []]]],
    ['Organization', []],
    ['Person', []],
  ]);
});
