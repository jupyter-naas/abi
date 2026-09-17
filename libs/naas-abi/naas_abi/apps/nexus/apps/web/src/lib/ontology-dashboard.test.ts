import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildOntologyDashboard, dashboardTerms, dashboardRoute, dashboardCoverage, dashboardOntologies, dashboardKindRoute, type OntologyDeclaration } from './ontology-dashboard';
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

test('coverage excludes display fallbacks, deduplicates shared declarations and scopes metadata to files', () => {
  const defined: DictionaryTerm = {...shared, metadata: {label:[a.path], definition:[b.path], example:[]}};
  const fallback: DictionaryTerm = {...property, description:'A comment fallback', definitions:[{value:'Comment',source_path:a.path}], metadata:{label:[],definition:[],example:[]}};
  const ontology: OntologyDeclaration = {id:'https://example.org/ontology',name:'Ontology',type:'ontology',sources:[a,b], metadata:{label:[a.path],definition:[],example:[a.path]}};
  const items = [defined, defined, fallback, ontology, hidden];
  const all = dashboardCoverage(items, [a.path,b.path]);
  assert.equal(all.total,3);
  assert.deepEqual(all.metrics.map(item => [item.present,item.missing,item.ratio]), [[2,1,2/3],[1,2,1/3],[1,2,1/3]]);
  assert.equal(dashboardCoverage(items,[a.path]).metrics[1].present,0);
  assert.equal(dashboardCoverage(items,[b.path]).total,2);
  assert.deepEqual(dashboardCoverage([],[]).metrics.map(item=>item.ratio),[null,null,null]);
  assert.equal(dashboardOntologies([ontology,ontology],[a.path]).length,1);
  assert.equal(dashboardOntologies([ontology],['/not-permitted.ttl']).length,0);
});

test('ontology KPI toggles and drill-down preserve workspace filters and navigation', () => {
  const base='view=overview&termFilter=entity&dictionaryFile=%2Fa.ttl&systemFilter=abi&spacing=compact';
  const ontology=dashboardKindRoute(base,'ontology');
  assert.equal(ontology.get('dashboardType'),'ontology');
  assert.equal(ontology.get('termFilter'),'all');
  assert.equal(dashboardKindRoute(ontology.toString(),'ontology').has('dashboardType'),false);
  const classes=dashboardKindRoute(ontology.toString(),'entity');
  assert.equal(classes.has('dashboardType'),false);
  assert.equal(classes.get('termFilter'),'entity');
  const file=dashboardRoute(ontology.toString(),a.path);
  assert.equal(file.has('dashboardType'),false);
  assert.equal(file.get('dashboardFile'),a.path);
  for (const result of [ontology,classes,file]) {
    assert.deepEqual(result.getAll('dictionaryFile'),['/a.ttl']);
    assert.deepEqual(result.getAll('systemFilter'),['abi']);
    assert.equal(result.get('spacing'),'compact');
  }
});
