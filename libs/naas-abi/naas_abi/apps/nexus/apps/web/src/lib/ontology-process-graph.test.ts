import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildProcessGraph, PROCESS_BUCKET_DEFS, processPresentationRoute } from './ontology-process-graph';
import { buildTermGraph } from './ontology-term-graph';
import { buildBucketTree } from './ontology-bucket-tree';
import type { DictionaryTerm } from './ontology-dictionary-tree';
const source = { path: 'allowed.ttl', name: 'Allowed', moduleName: 'test' };
const process: DictionaryTerm = {
  id: 'urn:onboarding', name: 'Onboarding', type: 'entity', sources: [source],
  processLedger: { code: 'S1-P1', buckets: { WHEN: [{ value: 'On hire', sources: [source] }], WHO: [{ value: 'HR system', sources: [source] }] } },
  parents: [{ id: 'http://purl.obolibrary.org/obo/BFO_0000015', name: 'process' }],
  relations: [{ property: { id: 'http://ontology.naas.ai/abi/hasExecutionCondition', name: 'has execution condition' }, target: { id: 'urn:condition', name: 'Timing condition' }, kind: 'restriction', constraint: 'some', sources: [source] }],
};
const condition: DictionaryTerm = { id: 'urn:condition', name: 'Timing condition', type: 'entity', sourceValues: ['On hire'], parents: [{ id: 'http://purl.obolibrary.org/obo/BFO_0000031', name: 'information' }] };

test('source presentation preserves words and omits hierarchy without changing the ontology', () => {
  const terms = [process, condition];
  const before = structuredClone(terms);
  const full = buildTermGraph(process, terms);
  const graph = buildProcessGraph(process, terms)!;
  assert.deepEqual(graph.nodes.map(node => node.label), ['S1-P1 · Onboarding', 'HR system', 'On hire']);
  assert.equal(graph.edges.length, 2);
  assert.ok(graph.edges.every(edge => edge.properties?.relation_kind === 'ledger'));
  assert.ok(full.edges.some(edge => edge.properties?.relation_kind === 'is_a'));
  assert.deepEqual(buildTermGraph(process, terms), full);
  assert.deepEqual(terms, before);
  assert.equal(graph.nodes[2].properties.formal_term_id, 'entity:urn:condition');
  assert.equal(graph.nodes[1].properties.formal_term_id, undefined);
});

test('a source timing entry keeps a presentation type separate from formal BFO classification', () => {
  const overview = buildProcessGraph(process, [process, condition])!;
  assert.equal(overview.nodes.find(node => node.label === 'On hire')!.type, 'ledger:WHEN');
  const full = buildTermGraph(process, [process, condition]);
  assert.equal(full.nodes.find(node => node.id === 'entity:urn:condition')!.type, 'GDC');
  const tree = buildBucketTree(overview.nodes, overview.edges, PROCESS_BUCKET_DEFS);
  assert.equal(tree.length, 7);
  assert.equal(tree.reduce((sum, bucket) => sum + bucket.count, 0), 3);
});

test('a same-label unrelated or unavailable class is not a formal drilldown target', () => {
  const graph = buildProcessGraph(process, [process, { ...condition, id: 'urn:unrelated' }])!;
  assert.equal(graph.nodes.find(node => node.label === 'On hire')!.properties.formal_term_id, undefined);
});

test('domain subproperties resolve to existing formal terms without hardcoded domain namespaces', () => {
  const participant: DictionaryTerm = {id: 'urn:person', name: 'Person', type: 'entity'};
  const relation: DictionaryTerm = {id: 'urn:company:participant', name: 'has participant', type: 'relationship', parents: [{id: 'http://purl.obolibrary.org/obo/BFO_0000057', name: 'has participant'}]};
  const domainProcess: DictionaryTerm = { ...process, processLedger: { buckets: { WHO: [{value: 'Person', sources: [source]}] } }, relations: [{property: {id: relation.id, name: relation.name}, target: {id: participant.id, name: participant.name}, kind: 'restriction', constraint: 'some', sources: [source]}] };
  const overview = buildProcessGraph(domainProcess, [domainProcess, participant, relation])!;
  assert.equal(overview.nodes[1].properties.formal_term_id, 'entity:urn:person');
  assert.equal(buildProcessGraph(domainProcess, [domainProcess, participant])!.nodes[1].properties.formal_term_id, undefined);
  const cyclic = { ...relation, parents: [{id: relation.id, name: relation.name}] };
  assert.equal(buildProcessGraph(domainProcess, [domainProcess, participant, cyclic])!.nodes[1].properties.formal_term_id, undefined);
});

test('terms without source bucket annotations retain the ordinary ontology view', () => {
  assert.equal(buildProcessGraph(condition, [condition]), null);
  assert.equal(buildProcessGraph({ ...process, processLedger: { buckets: {} } }, []), null);
});

test('mode switches preserve accumulated files and the selected system, subsystem and process', () => {
  const query = 'browser=dictionary&view=system&system=root&subsystem=personnel&process=onboarding&dictionaryFile=a.ttl&dictionaryFile=b.ttl';
  const detailed = processPresentationRoute(query, 'ontology');
  assert.equal(detailed.get('processView'), 'ontology');
  assert.deepEqual(detailed.getAll('dictionaryFile'), ['a.ttl', 'b.ttl']);
  assert.equal(detailed.get('process'), 'onboarding');
  assert.equal(processPresentationRoute(detailed.toString(), 'process').toString(), query);
});
