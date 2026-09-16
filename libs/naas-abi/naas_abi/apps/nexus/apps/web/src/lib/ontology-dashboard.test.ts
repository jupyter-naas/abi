import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildOntologyDashboard, dashboardTerms, dashboardRoute } from './ontology-dashboard';
import type { DictionaryTerm } from './ontology-dictionary-tree';

const a = {path:'/allowed/a.ttl',name:'A ontology',moduleName:'a'};
const b = {path:'/allowed/b.ttl',name:'B ontology',moduleName:'b'};
const empty = {path:'/allowed/empty.ttl',name:'Empty',moduleName:'b'};
const broken = {path:'/allowed/broken.ttl',name:'Broken',moduleName:'b'};
const shared: DictionaryTerm = {id:'https://example.org/shared',name:'Shared',type:'entity',sources:[a,b]};
const property: DictionaryTerm = {id:shared.id,name:'Shared property',type:'relationship',sources:[a]};
const hidden: DictionaryTerm = {id:'https://example.org/hidden',name:'Hidden',type:'entity',sources:[{path:'/unlisted.ttl',name:'Hidden',moduleName:'private'}]};

test('inventory controls tiles; missing, failed and empty ontologies stay distinct', () => {
  const tiles = buildOntologyDashboard([b,a,a,empty,broken],[shared,property,hidden],[broken.path]);
  assert.equal(tiles.length,4);
  assert.equal(tiles.some(tile=>tile.path==='/unlisted.ttl'),false);
  assert.equal(tiles.find(tile=>tile.path===empty.path)?.failed,false);
  assert.equal(tiles.find(tile=>tile.path===empty.path)?.terms.length,0);
  assert.equal(tiles.find(tile=>tile.path===broken.path)?.failed,true);
  assert.deepEqual(tiles.map(tile=>tile.moduleName),['a','b','b','b']);
});

test('shared terms count once across files; different kinds with the same IRI remain distinct', () => {
  const tiles = buildOntologyDashboard([a,b],[shared,shared,property]);
  assert.equal(tiles.find(tile=>tile.path===a.path)?.terms.length,2);
  assert.equal(tiles.find(tile=>tile.path===b.path)?.terms.length,1);
  assert.equal(dashboardTerms(tiles).length,2);
  assert.equal(dashboardTerms(tiles.filter(tile=>tile.path===b.path)).length,1);
});

test('tile indices do not depend on API response order', () => {
  assert.deepEqual(buildOntologyDashboard([a,b],[]),buildOntologyDashboard([b,a],[]));
});

test('dashboard drill-down preserves accumulated scope and visualization settings', () => {
  const query='browser=dictionary&view=system&system=system&subsystem=sub&process=p&term=t&termType=entity&dictionaryFile=%2Fa.ttl&dictionaryFile=%2Fb.ttl&systemFilter=system&connectors=orthogonal&spacing=compact&termFilter=annotation';
  const next=dashboardRoute(query,a.path);
  assert.equal(next.get('view'),'overview');
  assert.equal(next.get('dashboardFile'),a.path);
  assert.deepEqual(next.getAll('dictionaryFile'),['/a.ttl','/b.ttl']);
  assert.deepEqual(next.getAll('systemFilter'),['system']);
  assert.equal(next.get('termFilter'),'annotation');
  assert.equal(next.get('spacing'),'compact');
  assert.equal(next.get('connectors'),'orthogonal');
  for (const key of ['term','termType','system','subsystem','process']) assert.equal(next.has(key),false);
  assert.equal(dashboardRoute(next.toString()).has('dashboardFile'),false);
});
