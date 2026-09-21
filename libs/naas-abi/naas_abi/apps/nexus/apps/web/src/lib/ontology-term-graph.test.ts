import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildTermGraph, filterTermGraph } from './ontology-term-graph';
import { termKey } from './ontology-context';
import type { DictionaryTerm } from './ontology-dictionary-tree';

const source = { path: '/permitted/model.ttl', name: 'Model', moduleName: 'example' };
const bfo = (id: string, name: string): DictionaryTerm => ({ id: `http://purl.obolibrary.org/obo/BFO_${id}`, name, type: 'entity' });
const process = bfo('0000015', 'process');
const material = bfo('0000040', 'material entity');
const person: DictionaryTerm = { id: 'ex:Person', name: 'Person', type: 'entity', parents: [material] };
const root: DictionaryTerm = { id: 'ex:AddUser', name: 'Add User to Workspace', type: 'entity', parents: [process], relations: [
  { property: { id: 'ex:createdBy', name: 'created by' }, target: person, kind: 'restriction', constraint: 'only', sources: [source] },
  { property: { id: 'ex:updates', name: 'updates' }, target: person, kind: 'restriction', constraint: 'some', sources: [source] },
] };
const terms = [root, process, person, material];
const all = { hierarchy: true, restrictions: true, properties: true };

test('renders the selected class and properties as labelled edges, without duplicate property nodes', () => {
  const graph = buildTermGraph(root, terms);
  assert.equal(graph.rootId, termKey(root));
  assert(graph.edges.some(edge => edge.label === 'created by (only)'));
  assert(graph.edges.some(edge => edge.label === 'updates (some)'));
  assert(!graph.edges.some(edge => edge.label?.includes('uses property')));
  assert(!graph.nodes.some(node => node.properties.iri === 'ex:createdBy'));
  assert.deepEqual(graph.edges.find(edge => edge.label === 'updates (some)')?.properties?.source_files, [source]);
});

test('uses BFO ancestry from all permitted terms without adding the whole workspace to the graph', () => {
  const hidden: DictionaryTerm = { id: 'ex:Unrelated', name: 'Unrelated', type: 'entity' };
  const graph = buildTermGraph(root, [...terms, hidden]);
  assert.equal(graph.nodes.find(node => node.id === termKey(root))?.type, 'Process');
  assert.equal(graph.nodes.find(node => node.id === termKey(person))?.type, 'Material Entity');
  assert(!graph.nodes.some(node => node.id === termKey(hidden)));
  assert(!graph.nodes.some(node => node.id === termKey(material)));
});

test('ABI-style equivalent classes resolve to the specific BFO bucket', () => {
  const entity = bfo('0000001', 'entity');
  const occurrent: DictionaryTerm = { ...bfo('0000003', 'occurrent'), parents: [entity] };
  const alias: DictionaryTerm = { id: 'ex:Process', name: 'process', type: 'entity', parents: [occurrent], equivalents: [process] };
  const action = { ...root, parents: [alias] };
  const graph = buildTermGraph(action, [action, alias, occurrent, entity, process, person]);
  assert.equal(graph.nodes.find(node => node.id === graph.rootId)?.type, 'Process');
});

test('includes inherited domain/range properties and keeps their declaration provenance', () => {
  const property: DictionaryTerm = { id: 'ex:timestamp', name: 'timestamp', type: 'attribute', domain: [{ ...process, sources: [source] }], range: [{ id: 'http://www.w3.org/2001/XMLSchema#dateTime', name: 'dateTime', sources: [source] }] };
  const graph = buildTermGraph(root, [...terms, property]);
  const edge = graph.edges.find(edge => edge.label === 'timestamp · inherited');
  assert(edge);
  assert.equal(edge.source, termKey(root));
  assert.equal(edge.properties?.declared_on, 'process');
  assert.equal(edge.properties?.declaration, 'domain / range');
  assert(graph.nodes.some(node => node.label === 'dateTime'));
});

test('does not claim an inherited property has an explicitly declared child domain', () => {
  const property: DictionaryTerm = { id: 'ex:note', name: 'note', type: 'attribute', domain: [process] };
  const graph = buildTermGraph(root, [...terms, property]);
  assert(graph.edges.some(edge => edge.target === termKey(property) && edge.label === 'inherits property'));
  assert(!graph.edges.some(edge => edge.source === termKey(property) && edge.target === termKey(root) && edge.label === 'has domain'));
});

test('property terms show their domain and range; individuals keep instance-of semantics', () => {
  const property: DictionaryTerm = { id: 'ex:agent', name: 'agent', type: 'relationship', domain: [process], range: [person] };
  const graph = buildTermGraph(property, [...terms, property]);
  assert(graph.edges.some(edge => edge.source === termKey(property) && edge.label === 'has domain'));
  assert(graph.edges.some(edge => edge.source === termKey(property) && edge.label === 'has range'));
  const individual: DictionaryTerm = { id: 'ex:Jane', name: 'Jane', type: 'individual', parents: [person] };
  const instance = buildTermGraph(individual, [...terms, individual]);
  assert(instance.edges.some(edge => edge.source === termKey(individual) && edge.label === 'instance of' && edge.properties?.relation_kind === 'hierarchy'));
});

test('relation toggles hide disconnected targets and retain the selected term', () => {
  const graph = buildTermGraph(root, terms);
  const none = filterTermGraph(graph, { hierarchy: false, restrictions: false, properties: false });
  assert.deepEqual(none.nodes.map(node => node.id), [graph.rootId]);
  assert.equal(none.edges.length, 0);
  const onlyHierarchy = filterTermGraph(graph, { ...all, restrictions: false });
  assert(!onlyHierarchy.nodes.some(node => node.id === termKey(person)));
  const people = filterTermGraph(graph, all, new Set(['Material Entity']));
  assert.deepEqual(new Set(people.nodes.map(node => node.id)), new Set([termKey(root), termKey(person)]));
  const hidden = filterTermGraph(graph, all, new Set(), new Set([termKey(person)]));
  assert(!hidden.edges.some(edge => edge.source === termKey(person) || edge.target === termKey(person)));
});

test('does not truncate the term to six neighbours or collapse punned term types', () => {
  const children: DictionaryTerm[] = Array.from({ length: 12 }, (_, i) => ({ id: `ex:Child${i}`, name: `Child ${i}`, type: 'entity', parents: [root] }));
  const graph = buildTermGraph(root, [...terms, ...children]);
  assert.equal(graph.nodes.filter(node => String(node.properties.iri).startsWith('ex:Child')).length, 12);
  const punned: DictionaryTerm = { ...root, type: 'individual', parents: [root], relations: [] };
  const instance = buildTermGraph(punned, [...terms, punned]);
  assert(instance.nodes.some(node => node.id === termKey(root)));
  assert(instance.nodes.some(node => node.id === termKey(punned)));
});

test('cycles terminate and remain represented without cyclic tree-layout edges', () => {
  const a: DictionaryTerm = { id: 'ex:A', name: 'A', type: 'entity', parents: [{ id: 'ex:B', name: 'B' }] };
  const b: DictionaryTerm = { id: 'ex:B', name: 'B', type: 'entity', parents: [a] };
  const graph = buildTermGraph(a, [a, b]);
  assert.equal(graph.nodes.length, 2);
  assert.equal(graph.edges.length, 2);
  assert.equal(graph.edges.filter(edge => edge.properties?.relation_kind === 'is_a').length, 1);
});
