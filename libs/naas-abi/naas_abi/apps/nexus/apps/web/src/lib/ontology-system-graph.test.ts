import test from 'node:test';
import assert from 'node:assert/strict';
import { buildOntologySystems, buildSystemGraph, buildSystemsGraph } from './ontology-system-graph';
import { systemRoute, termRoute, browserRoute, normalizeOntologyRoute } from './ontology-navigation';
import { filterTermsByFiles } from './ontology-file-filter';
import type { DictionaryTerm } from './ontology-dictionary-tree';

const source = (path: string) => ({ path, name: path, moduleName: 'fixture' });
const term = (id: string, fields: Partial<DictionaryTerm> = {}): DictionaryTerm => ({ id, name: id, type: 'entity', sources: [source(id + '.ttl')], ...fields });
const root = term('system', { systemViewKind: 'system' });
const group = term('group', { systemViewKind: 'subsystem', systemViewParents: [{ id: root.id, name: root.name }] });
const process = term('p1', { parents: [{ id: 'http://purl.obolibrary.org/obo/BFO_0000015', name: 'process' }, { id: root.id, name: root.name }, { id: group.id, name: group.name }] });
const second = term('p2', { parents: process.parents });
const terms = [root, group, process, second];

const sampleProcesses = ['Engage process', 'Deliver process', 'Manage process', 'Develop process', 'Comply process'].map((name, index) => term('proc' + index, {
  name, parents: [{id: root.id, name: root.name}, {id: 'http://purl.obolibrary.org/obo/BFO_0000015', name: 'process'}],
}));

test('five processes fit at readable text size instead of using a large-ledger radius', () => {
  const [model] = buildOntologySystems([root, ...sampleProcesses]);
  const original = structuredClone(model);
  const graph = buildSystemGraph(model);
  const width = Math.max(...graph.nodes.map(node => node.x!)) - Math.min(...graph.nodes.map(node => node.x!)) + 220;
  const height = Math.max(...graph.nodes.map(node => node.y!)) - Math.min(...graph.nodes.map(node => node.y!)) + 80;
  // vis-network fit adds 10% padding; a modest canvas should retain 1:1 text.
  assert.ok(width * 1.1 <= 800, `Too wide for legible fit: ${width}`);
  assert.ok(height * 1.1 <= 500, `Too tall for legible fit: ${height}`);
  assert.equal(graph.nodes.length, 6);
  assert.equal(graph.edges.length, 5);
  for (const [index, a] of graph.nodes.entries()) for (const b of graph.nodes.slice(index + 1)) {
    assert.ok(Math.abs(a.x! - b.x!) >= 210 || Math.abs(a.y! - b.y!) >= 80, 'Process labels must remain separated');
  }
  assert.deepEqual(model, original);
});

test('multiple small systems use their actual bounds instead of fixed 3000-unit gaps', () => {
  const [first] = buildOntologySystems([root, ...sampleProcesses]);
  const other = term('other', {systemViewKind: 'system'});
  const children = sampleProcesses.map(p => ({...p, id: p.id + 'other', parents: [{id: other.id, name: other.name}, ...p.parents!.slice(1)]}));
  const [second] = buildOntologySystems([other, ...children]);
  const graph = buildSystemsGraph([first, second]);
  assert.equal(graph.nodes.length, 12);
  assert.equal(graph.edges.length, 10);
  const firstRight = Math.max(...graph.nodes.filter(node => first.term.id === node.properties.iri || first.processes.some(p => p.id === node.properties.iri)).map(node => node.x! + 110));
  const secondLeft = Math.min(...graph.nodes.filter(node => second.term.id === node.properties.iri || second.processes.some(p => p.id === node.properties.iri)).map(node => node.x! - 110));
  assert.ok(secondLeft > firstRight, 'Selected systems must not overlap');
  assert.ok(Math.max(...graph.nodes.map(node => node.x!)) - Math.min(...graph.nodes.map(node => node.x!)) < 1600);
});

test('combined overview includes every selected system, with separate layouts and no synthetic root', () => {
  const sibling = term('sibling', { systemViewKind: 'system' });
  const engage = term('engage', { parents: [{id: sibling.id, name: sibling.name}, {id: 'http://purl.obolibrary.org/obo/BFO_0000015', name: 'process'}] });
  const systems = buildOntologySystems([...terms, sibling, engage]);
  const graph = buildSystemsGraph(systems);
  assert.equal(graph.nodes.length, 6);
  assert.equal(graph.edges.length, 4);
  assert.equal(graph.nodes.filter(node => node.properties.system_level === 'system').length, 2);
  assert.notEqual(graph.nodes.find(n => n.id === 'entity:sibling')?.x, graph.nodes.find(n => n.id === 'entity:system')?.x);
  assert.deepEqual(buildSystemsGraph([systems[0]]), buildSystemGraph(systems[0]));
  assert.deepEqual(buildSystemsGraph([]), { nodes: [], edges: [] });
});

test('system → subsystem → processes is distinct from the ontology ancestor graph', () => {
  const [model] = buildOntologySystems(terms);
  const graph = buildSystemGraph(model);
  assert.equal(model.subsystems.length, 1);
  assert.equal(model.processes.length, 2);
  assert.equal(graph.nodes.length, 4);
  assert.equal(graph.edges.length, 3);
  assert(graph.edges.some(edge => edge.source === 'entity:system' && edge.target === 'entity:group'));
  assert(!graph.edges.some(edge => edge.source === 'entity:system' && edge.target === 'entity:p1'));
  assert(graph.nodes.every(node => Number.isFinite(node.x) && Number.isFinite(node.y)));
  const drilled = buildSystemGraph(model, 'group');
  assert.equal(drilled.rootId, 'entity:group');
  assert.equal(drilled.nodes.length, 3);
});

test('file checkboxes constrain process membership while retaining visible grouping context', () => {
  const [one] = buildOntologySystems(terms, filterTermsByFiles(terms, ['p1.ttl']));
  assert.deepEqual(one.processes.map(term => term.id), ['p1']);
  assert.equal(one.subsystems.length, 1);
  const [both] = buildOntologySystems(terms, filterTermsByFiles(terms, ['p1.ttl', 'p2.ttl']));
  assert.equal(both.processes.length, 2);
  assert.equal(buildOntologySystems(terms, [])[0].processes.length, 0);
});

test('never discovers systems or groups through unprovided files', () => {
  assert.equal(buildOntologySystems([group, process]).length, 0);
  const [partial] = buildOntologySystems([root, process]);
  assert.equal(partial.subsystems.length, 0);
  assert.equal(partial.ungrouped.length, 1);
  assert(!buildSystemGraph(partial).nodes.some(node => node.id === 'entity:group'));
  assert.equal(buildOntologySystems([term('unmarked'), process]).length, 0);
});

test('multiple subgroup membership creates one process node and retains both edges', () => {
  const other = term('group2', { systemViewKind: 'subsystem', systemViewParents: group.systemViewParents });
  const shared = { ...process, parents: [...process.parents!, { id: other.id, name: other.name }] };
  const [model] = buildOntologySystems([root, group, other, shared]);
  const graph = buildSystemGraph(model);
  assert.equal(model.processes.length, 1);
  assert.equal(graph.nodes.filter(node => node.id === 'entity:p1').length, 1);
  assert.equal(graph.edges.filter(edge => edge.target === 'entity:p1').length, 2);
});

test('cyclic class ancestry cannot hang or turn an annotation into a process', () => {
  const a = term('a', { parents: [{ id: 'b', name: 'b' }, { id: root.id, name: root.name }] });
  const b = term('b', { parents: [{ id: 'a', name: 'a' }] });
  const annotation = { ...process, id: 'annotation', type: 'annotation' as const };
  assert.equal(buildOntologySystems([root, group, a, b, annotation])[0].processes.length, 0);
});

test('System row clears the selected term and keeps accumulated file scope', () => {
  const query = 'browser=dictionary&view=network&term=annotation&termType=annotation&termFilter=annotation&dictionaryFile=a&dictionaryFile=b';
  const next = systemRoute(query, 'system', 'group', 'p1');
  assert.equal(next.get('view'), 'system');
  assert.equal(next.get('term'), null);
  assert.equal(next.get('termType'), null);
  assert.deepEqual(next.getAll('dictionaryFile'), ['a', 'b']);
  assert.equal(next.get('termFilter'), 'annotation');
  assert.equal(normalizeOntologyRoute(next.toString()).get('process'), 'p1');
  const reset = systemRoute(next.toString());
  assert.equal(reset.get('process'), null);
  assert.equal(reset.get('subsystem'), null);
  assert.equal(reset.get('system'), null);
  const selected = termRoute(next.toString(), process);
  assert.equal(selected.get('view'), 'classes');
  assert.equal(selected.get('system'), null);
  const files = browserRoute(next.toString(), 'files');
  assert.equal(files.get('view'), 'network');
  assert.equal(files.get('process'), null);
});
