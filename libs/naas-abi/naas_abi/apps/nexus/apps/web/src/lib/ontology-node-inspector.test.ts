import { test } from 'node:test';
import assert from 'node:assert/strict';
import { inspectorTerm, inspectorConnections, inspectorSources } from './ontology-node-inspector';
import type { DictionaryTerm } from './ontology-dictionary-tree';
import type { GraphNode, GraphEdge } from '../stores/knowledge-graph';
const term: DictionaryTerm = { id: 'urn:a', name: 'A', type: 'entity' };
const node: GraphNode = { id: 'entity:urn:a', label: 'A', type: 'Process', properties: {} };
test('full page resolves the named kind, including punned IRIs', () => {
  assert.equal(inspectorTerm(node, [{ ...term, type: 'relationship' }, term]), term);
  assert.equal(inspectorTerm({ ...node, id: 'reference:urn:a' }, [term]), undefined);
});
test('ledger entries only resolve an explicitly linked formal term', () => {
  const ledger = { ...node, id: 'ledger:a', properties: { presentation_only: true } };
  assert.equal(inspectorTerm(ledger, [term]), undefined);
  assert.equal(inspectorTerm({ ...ledger, properties: { formal_term_id: node.id } }, [term]), term);
  assert.equal(inspectorTerm({ ...ledger, properties: { formal_term_id: 'entity:urn:hidden' } }, [term]), undefined);
});
test('incoming and outgoing relations keep their direction and only link available graph nodes', () => {
  const b = { ...node, id: 'entity:urn:b', label: 'B' };
  const edges: GraphEdge[] = [
    { id: '1', source: node.id, target: b.id, type: 'is_a', label: 'subclass of' },
    { id: '2', source: b.id, target: node.id, type: 'relation', label: 'uses' },
    { id: '3', source: node.id, target: 'missing', type: 'relation' },
  ];
  const result = inspectorConnections(node, [node, b], edges);
  assert.deepEqual(result.map(item => [item.edge.label, item.incoming, item.other.label]), [['subclass of', false, 'B'], ['uses', true, 'B']]);
});
test('provenance keeps ledger and ontology sources without duplicates or malformed paths', () => {
  const source = { path: 'process.ttl', name: 'Process', moduleName: 'test' };
  const shared = { ...source, path: 'shared.ttl' };
  assert.deepEqual(inspectorSources({ ...node, properties: { source_files: [source, null, { path: 42 }] } }, { ...term, sources: [source, shared] }), [source, shared]);
});
