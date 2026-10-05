import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildFileNetwork, type ProcessSlice } from './ontology-file-network';
import { dashboardRestrictions } from './ontology-dashboard';
import type { DictionaryTerm } from './ontology-dictionary-tree';

const BFO = 'http://purl.obolibrary.org/obo/';
const file = { path: '/m/ontologies/modules/People.ttl', name: 'People', moduleName: 'people' };
const restriction = (property: string, id: string, name: string, bucket?: string) =>
  ({ property: { id: property, name: property }, target: { id, name, bfoBucket: bucket }, kind: 'restriction' as const, constraint: 'some', sources: [file] });
const work: DictionaryTerm = { id: 'people:ActOfWorking', name: 'Act of Working', type: 'entity', sources: [file], bfoBucket: `${BFO}BFO_0000015`,
  relations: [restriction('abi:occursIn', 'abi:GeospatialRegion', 'geospatial region', `${BFO}BFO_0000029`), restriction('abi:hasParticipant', 'abi:Person', 'Person')] };
const study: DictionaryTerm = { id: 'people:ActOfStudying', name: 'Act of Studying', type: 'entity', sources: [file], bfoBucket: `${BFO}BFO_0000015`,
  relations: [restriction('abi:occursIn', 'abi:GeospatialRegion', 'geospatial region', `${BFO}BFO_0000029`)] };
const person: DictionaryTerm = { id: 'abi:Person', name: 'Person', type: 'entity', sources: [{ ...file, path: '/abi.ttl' }], bfoBucket: `${BFO}BFO_0000040` };
const skill: DictionaryTerm = { id: 'people:Skill', name: 'Skill', type: 'entity', sources: [file], bfoBucket: `${BFO}BFO_0000019` };
const all = [work, study, person, skill];
const fileTerms = [work, study, skill];
const restrictions = dashboardRestrictions(all, [file.path]);
const slices: ProcessSlice[] = [
  { id: 'urn:Working', name: 'Working', path: '/m/ontologies/processes/Working.ttl', classes: ['people:ActOfWorking', 'abi:Person'],
    restrictions: [{ subject: 'people:ActOfWorking', property: 'abi:occursIn', target: 'abi:GeospatialRegion' }, { subject: 'people:ActOfWorking', property: 'abi:hasParticipant', target: 'abi:Person' }] },
  { id: 'urn:Studying', name: 'Studying', path: '/m/ontologies/processes/Studying.ttl', classes: ['people:ActOfStudying'],
    restrictions: [{ subject: 'people:ActOfStudying', property: 'abi:occursIn', target: 'abi:GeospatialRegion' }] },
];
const labels = (network: ReturnType<typeof buildFileNetwork>) => network.nodes.map(node => node.label).sort();

test('the whole file: every declared class, and the classes its restrictions reach, in their buckets', () => {
  const network = buildFileNetwork(fileTerms, restrictions, all);
  assert.deepEqual(labels(network), ['Act of Studying', 'Act of Working', 'Person', 'Skill', 'geospatial region']);
  assert.equal(network.edges.length, 3);
  const types = Object.fromEntries(network.nodes.map(node => [node.label, node.type]));
  assert.equal(types['Act of Working'], 'Process');
  assert.equal(types['geospatial region'], 'Site');
  assert.equal(types.Person, 'Material Entity');
  assert.ok(network.edges.every(edge => edge.properties?.relation_kind === 'restriction'));
});

test('selected processes keep only what their slices state', () => {
  const working = buildFileNetwork(fileTerms, restrictions, all, slices, new Set(['urn:Working']));
  assert.deepEqual(labels(working), ['Act of Working', 'Person', 'geospatial region']);
  assert.equal(working.edges.length, 2);
  const both = buildFileNetwork(fileTerms, restrictions, all, slices, new Set(['urn:Working', 'urn:Studying']));
  assert.equal(both.edges.length, 3);
  assert.equal(labels(both).includes('Skill'), false);
});
