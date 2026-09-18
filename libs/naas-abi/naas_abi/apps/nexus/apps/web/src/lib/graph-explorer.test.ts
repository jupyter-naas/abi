import assert from 'node:assert/strict';
import {test} from 'node:test';
import {classTerms,explorerQuery,explorerScope,graphMode,groupComposerViews,toggleValue} from './graph-explorer';
import {buildDictionaryTree} from './ontology-dictionary-tree';

test('Explorer defaults to dashboard and supports direct instance links', () => {
  assert.equal(explorerScope('').dashboard,true);
  assert.equal(explorerScope('class=urn%3APerson').dashboard,false);
  assert.equal(explorerScope('view=instances').dashboard,false);
});
test('URI filters accumulate, deduplicate and preserve layout', () => {
  const query = explorerQuery('list=hierarchy&graph=urn%3Aa&class=urn%3APerson',{graph:['urn:a','urn:b'],class:null});
  assert.deepEqual(explorerScope(query),{graphs:['urn:a','urn:b'],classes:[],activeClass:'',hierarchy:true,dashboard:true,view:'instances'});
  assert.deepEqual(toggleValue(['a','b'],'a'),['b']);
  assert.deepEqual(toggleValue(['a'],'b'),['a','b']);
  assert.deepEqual(explorerScope('graph=a&graph=a').graphs,['a']);
});
test('class filters and canvas selection stay distinct, dashboard clears both explicitly', () => {
  const query = 'classFilter=urn%3AA&classFilter=urn%3AB&class=urn%3AA&view=instances&graph=urn%3Ag';
  assert.deepEqual(explorerScope(query).classes,['urn:A','urn:B']);
  const dashboard = explorerScope(explorerQuery(query,{classFilter:null,class:null,view:null}));
  assert.equal(dashboard.dashboard,true);assert.deepEqual(dashboard.graphs,['urn:g']);
});
test('Composer and legacy URLs use the same saved-view sidebar', () => {
  for (const view of ['composer','explore-next','explore']) assert.equal(graphMode(`/workspace/ws/graph/${view}`),'composer');
  assert.equal(graphMode('/workspace/ws/graph/explorer'),'explorer');
  assert.equal(graphMode('/workspace/ws/graph/network'),'explorer');
});
test('saved views retain paths, IDs and sort order without mutating their source', () => {
  const source=[{id:'2',path:'Team/Finance',name:null,label:'Z'},{id:'1',path:'Team/Finance',name:'A',label:'fallback'},{id:'0',path:'',label:'Root'}];
  const result=groupComposerViews(source);
  assert.equal(result[0].path,'');assert.deepEqual(result[1].views.map(v=>v.id),['1','2']);
  assert.deepEqual(source.map(v=>v.id),['2','1','0']);
});
test('hierarchy preserves URI identity and survives cycles and duplicate class names', () => {
  const terms=classTerms([{uri:'a',label:'Person',count:2,parents:['b']},{uri:'b',label:'Person',count:3,parents:['a']}]);
  const tree=buildDictionaryTree(terms);assert.equal(tree.length,1);assert.equal(tree[0].children.length,1);
  assert.notEqual(tree[0].id,tree[0].children[0].id);
});


test('Explorer tabs preserve the graph and class selection, including direct links', () => {
  const query = 'graph=urn%3AA&graph=urn%3AB&class=urn%3APerson&classFilter=urn%3APerson&list=hierarchy';
  for (const view of ['instances', 'network', 'details']) {
    const scope = explorerScope(explorerQuery(query, { view }));
    assert.equal(scope.view, view);
    assert.equal(scope.dashboard, false);
    assert.deepEqual(scope.graphs, ['urn:A', 'urn:B']);
    assert.equal(scope.activeClass, 'urn:Person');
    assert.deepEqual(scope.classes, ['urn:Person']);
    assert.equal(scope.hierarchy, true);
  }
  assert.equal(explorerScope('view=network').dashboard, false);
  assert.equal(explorerScope('view=unrecognized').dashboard, true);
});
