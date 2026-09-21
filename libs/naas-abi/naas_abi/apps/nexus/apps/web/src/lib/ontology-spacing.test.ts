import test from 'node:test';
import assert from 'node:assert/strict';
import { ONTOLOGY_SPACING, ontologySpacing, ontologySpacingRoute, spaceOntologyNodes } from './ontology-spacing';
import type { GraphNode } from '../stores/knowledge-graph';

test('spacing menu preserves accumulated filters and inspection when changing distance', () => {
  const query = 'browser=dictionary&view=system&systemFilter=abi&systemFilter=beta&dictionaryFile=a&dictionaryFile=b&system=abi&subsystem=s1&process=p1&term=t1&termType=entity&connectors=curved&processView=ontology';
  for (const option of ONTOLOGY_SPACING) {
    const next = ontologySpacingRoute(query, option.value);
    assert.equal(ontologySpacing(next.toString()), option);
    next.delete('spacing');
    assert.equal(next.toString(), query);
  }
  assert.equal(ontologySpacing('spacing=invalid').value, 'compact');
  assert.equal(ontologySpacing('').value, 'compact');
});

test('system and process overviews spread positions without scaling boxes or losing identity', () => {
  const nodes: GraphNode[] = [
    {id: 'root', label: 'System', type: 'Process', properties: {is_primary: true}, x: 0, y: 0, size: 32},
    {id: 'a', label: 'Process', type: 'Process', properties: {}, x: 240, y: -120, size: 32},
    {id: 'b', label: 'Process', type: 'Process', properties: {}, x: -200, y: 80},
    {id: 'unpositioned', label: 'Term', type: 'Entity', properties: {}},
  ];
  const original = structuredClone(nodes);
  assert.equal(spaceOntologyNodes(nodes, 1), nodes);
  const expanded = spaceOntologyNodes(nodes, ontologySpacing('spacing=spacious').scale);
  assert.equal(expanded[1].x, 408); assert.equal(expanded[1].y, -204);
  assert.equal(expanded[1].size, 32);
  assert.equal(expanded[3].x, undefined);
  assert.deepEqual(nodes, original);
  assert.deepEqual(expanded.map(node => [node.id, node.label, node.properties]), nodes.map(node => [node.id, node.label, node.properties]));
});
