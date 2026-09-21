import test from 'node:test';
import assert from 'node:assert/strict';
import type { GraphNode, GraphEdge } from '../stores/knowledge-graph';
import { buildBucketTree, filterBucketTree, type BucketTreeNode } from './ontology-bucket-tree';

const node = (id: string, type = 'Process'): GraphNode => ({ id, label: id, type, properties: {} });
const edge = (source: string, target: string, relation_kind = 'is_a'): GraphEdge => ({ id: `${source}:${target}`, source, target, type: relation_kind, properties: { relation_kind } });
const flatten = (entries: BucketTreeNode[]): string[] => entries.flatMap(entry => [entry.node.id, ...flatten(entry.children)]);

test('overview follows system → subsystem → process grouping and keeps seven bucket headings', () => {
  const tree = buildBucketTree(['system', 'group', 'process'].map(id => node(id)), [edge('system', 'group', 'system_group'), edge('group', 'process', 'system_group')]);
  assert.equal(tree.length, 7);
  const what = tree.find(group => group.bucket.label === 'What')!;
  assert.equal(what.count, 3);
  assert.equal(what.roots[0].node.id, 'system');
  assert.equal(what.roots[0].children[0].children[0].node.id, 'process');
  assert.equal(tree.find(group => group.bucket.label === 'Who')!.count, 0);
});

test('a process appears once under its specific parent, with participants in their own bucket', () => {
  const tree = buildBucketTree([node('process'), node('group'), node('root'), node('person', 'Material Entity')], [edge('process', 'root'), edge('process', 'group'), edge('group', 'root'), edge('process', 'person', 'restriction')]);
  const what = tree.find(group => group.bucket.label === 'What')!;
  assert.equal(what.roots[0].children[0].node.id, 'group');
  assert.equal(what.roots[0].children[0].children[0].node.id, 'process');
  assert.deepEqual(flatten(what.roots), ['root', 'group', 'process']);
  assert.deepEqual(flatten(tree.find(group => group.bucket.label === 'Who')!.roots), ['person']);
});

test('cycles and multiple parents cannot omit or endlessly duplicate a graph element', () => {
  const tree = buildBucketTree(['a', 'b', 'c'].map(id => node(id)), [edge('a', 'b'), edge('b', 'a'), edge('c', 'a'), edge('c', 'b')]);
  assert.deepEqual(tree.flatMap(group => flatten(group.roots)).sort(), ['a', 'b', 'c']);
});

test('search retains ancestry and does not invent missing graph nodes', () => {
  const tree = buildBucketTree(['system', 'finance', 'approval', 'invoice'].map(id => node(id)), [edge('finance', 'system'), edge('approval', 'finance'), edge('invoice', 'finance'), edge('secret', 'finance')]);
  const found = filterBucketTree(tree, 'approval');
  assert.deepEqual(found.flatMap(group => flatten(group.roots)), ['system', 'finance', 'approval']);
  assert.equal(filterBucketTree(tree, 'secret').length, 0);
  assert.equal(filterBucketTree(tree, 'what')[0].count, 4);
});

test('unclassified references remain separate from the seven populated or empty buckets', () => {
  const tree = buildBucketTree([node('generic', 'Entity'), node('unclassified', 'Unknown')], []);
  assert.equal(tree.length, 9);
  assert.equal(tree.find(group => group.bucket.type === 'Quality')!.count, 0);
  assert.deepEqual(flatten(tree.find(group => group.bucket.type === 'Unknown')!.roots), ['unclassified']);
});
