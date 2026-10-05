import { test } from 'node:test';
import assert from 'node:assert/strict';
import { groupClassesByBfoBucket, referencedClasses } from './ontology-bfo-groups';
import type { DictionaryNode, DictionaryTerm } from './ontology-dictionary-tree';

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

test('classes nest under their nearest same-bucket ancestor reached through imports', () => {
  const CCO = 'https://www.commoncoreontologies.org/';
  const process: DictionaryTerm = { id: 'abi:Process', name: 'process', type: 'entity',
    equivalents: [{ id: `${BFO}BFO_0000015`, name: 'process' }], bfoBucket: `${BFO}BFO_0000015`, bfoAncestors: [`${BFO}BFO_0000015`, `${BFO}BFO_0000003`] };
  const study: DictionaryTerm = { id: 'people:ActOfStudying', name: 'Act of Studying', type: 'entity',
    parents: [{ id: `${CCO}ont00000228`, name: 'Planned Act' }], bfoBucket: `${BFO}BFO_0000015`,
    bfoAncestors: [`${CCO}ont00000228`, `${CCO}ont00000005`, `${BFO}BFO_0000015`, `${BFO}BFO_0000003`] };
  const material: DictionaryTerm = { id: 'abi:MaterialEntity', name: 'material entity', type: 'entity',
    equivalents: [{ id: `${BFO}BFO_0000040`, name: 'material entity' }], bfoBucket: `${BFO}BFO_0000040`, bfoAncestors: [`${BFO}BFO_0000040`, `${BFO}BFO_0000004`] };
  // abi:Person and CCO Person are equivalent: neither may become the other's parent.
  const pers: DictionaryTerm = { id: 'abi:Person', name: 'Person', type: 'entity', equivalents: [{ id: `${CCO}ont00001262`, name: 'Person' }],
    bfoBucket: `${BFO}BFO_0000040`, bfoAncestors: [`${CCO}ont00001262`, `${CCO}ont00000562`, `${BFO}BFO_0000040`] };
  const ccoPerson: DictionaryTerm = { id: `${CCO}ont00001262`, name: 'CCO Person', type: 'entity',
    bfoBucket: `${BFO}BFO_0000040`, bfoAncestors: [`${CCO}ont00000562`, `${BFO}BFO_0000040`, 'abi:Person'] };
  const all = [process, study, material, pers, ccoPerson];
  const groups = groupClassesByBfoBucket(all, all);
  const shape = (nodes: DictionaryNode[]): unknown => nodes.map(node => [node.name, shape(node.children)]);
  const tree = (type: string) => shape(groups.find(group => group.bucket.type === type)!.tree);
  assert.deepEqual(tree('Process'), [['process', [['Act of Studying', []]]]]);
  assert.deepEqual(tree('Material Entity'), [['material entity', [['CCO Person', []], ['Person', []]]]]);
});

test('classes the selection only references are grouped, flagged referenced', () => {
  const site: DictionaryTerm = { id: 'abi:Site', name: 'site', type: 'entity', equivalents: [{ id: `${BFO}BFO_0000029`, name: 'site' }], bfoBucket: `${BFO}BFO_0000029` };
  const study: DictionaryTerm = { id: 'people:ActOfStudying', name: 'Act of Studying', type: 'entity', bfoBucket: `${BFO}BFO_0000015`,
    relations: [
      { property: { id: 'abi:occursIn', name: 'occurs in' }, kind: 'restriction', sources: [],
        target: { id: 'cco:ont00000270', name: 'Educational Facility', bfoBucket: `${BFO}BFO_0000040`, bfoAncestors: [`${BFO}BFO_0000040`] } },
      { property: { id: 'abi:occursIn', name: 'occurs in' }, kind: 'restriction', sources: [], target: { id: 'abi:Site', name: 'site' } },
    ] };
  const groups = groupClassesByBfoBucket([study], [study, site]);
  const material = groups.find(group => group.bucket.type === 'Material Entity')!;
  assert.deepEqual(material.terms.map(term => [term.name, term.referenced]), [['Educational Facility', true]]);
  // Declared in another file: listed from its workspace declaration, still flagged referenced.
  assert.deepEqual(groups.find(group => group.bucket.type === 'Site')!.terms.map(term => [term.name, term.referenced, term.equivalents?.length]), [['site', true, 1]]);
  // Once selected, a target is not duplicated.
  const both = groupClassesByBfoBucket([study, site], [study, site]);
  assert.deepEqual(both.find(group => group.bucket.type === 'Site')!.terms.map(term => [term.name, term.referenced]), [['site', undefined]]);
});

test('restrictions a file states on classes declared elsewhere bring their targets in', () => {
  const region: DictionaryTerm = { id: 'abi:GeospatialRegion', name: 'Geospatial Region', type: 'entity', bfoBucket: `${BFO}BFO_0000029` };
  const file = { path: 'people/PeopleOntology.ttl', name: 'People', moduleName: 'people' };
  const work: DictionaryTerm = { id: 'people:ActOfWorking', name: 'Act of Working', type: 'entity', sources: [{ path: 'abi/ABIOntology.ttl', name: 'ABI', moduleName: 'abi' }],
    relations: [{ property: { id: 'abi:occursIn', name: 'occurs in' }, kind: 'restriction', constraint: 'some', sources: [file], target: { id: region.id, name: region.name } }] };
  assert.deepEqual(referencedClasses([], [work, region], [file.path]).map(term => [term.id, term.referenced]), [['abi:GeospatialRegion', true]]);
  assert.deepEqual(referencedClasses([], [work, region], ['other.ttl']), []);
});
