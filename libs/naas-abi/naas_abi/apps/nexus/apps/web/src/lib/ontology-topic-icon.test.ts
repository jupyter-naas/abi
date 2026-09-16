import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ontologyTopicIcon } from './ontology-topic-icon';
import { ONTOLOGY_TOPIC_GLYPHS } from './ontology-topic-glyphs';

test('ontology topics use their matching Material Symbols Light glyphs', () => {
  for (const [name, icon] of [
    ['Currency Unit Ontology','payments-outline'], ['Geospatial Ontology','public'],
    ['S8-P1 · Finance approval chain','account-balance-outline'], ['Security screening','security'],
    ['ABI AI System','smart-toy-outline'], ['Nexus AI System','smart-toy-outline'],
    ['AI agents','smart-toy-outline'], ['Human resources','groups-outline'],
    ['Audit trail maintenance','policy-outline'], ['Onboarding','badge-outline'], ['temporal region','schedule-outline'],
    ['Information Entity Ontology','description-outline'], ['Units of Measure Ontology','straighten'],
    ['ABIS3P3FleetDispatch.ttl','local-shipping-outline'], ['A new vocabulary','schema-outline'],
  ]) assert.equal(ontologyTopicIcon({name}),icon,name);
});

test('term labels take priority over their source ontology topic', () => {
  assert.equal(ontologyTopicIcon({name:'Security screening', sources:[{name:'ABI Ontology',path:'/allowed/ABIOntology.ttl',moduleName:'abi'}]}),'security');
});

test('fallbacks handle property kinds, unknown names and missing metadata', () => {
  assert.equal(ontologyTopicIcon({name:'x',type:'relationship'}),'link');
  assert.equal(ontologyTopicIcon({name:'x',type:'attribute'}),'checklist');
  assert.equal(ontologyTopicIcon({name:'x',type:'annotation'}),'description-outline');
  assert.equal(ontologyTopicIcon({name:'x',type:'individual'}),'person-outline');
  assert.equal(ontologyTopicIcon({name:'',path:'/Users/finance/security/Unknown.ttl'}),'schema-outline');
  assert.equal(ontologyTopicIcon({name:'x',parents:[{name:'person'}]}),'person-outline');
});

test('reordered sources do not change the icon', () => {
  const sources=[{name:'Geospatial Ontology',path:'/a.ttl',moduleName:'cco'},{name:'Currency Ontology',path:'/b.ttl',moduleName:'cco'}];
  assert.equal(ontologyTopicIcon({name:'x',sources}),ontologyTopicIcon({name:'x',sources:[...sources].reverse()}));
});

test('word boundaries prevent accidental topic matches inside unrelated words', () => {
  assert.equal(ontologyTopicIcon({name:'Display'}),'schema-outline');
  assert.equal(ontologyTopicIcon({name:'Brainstorming'}),'schema-outline');
});

test('the bundled glyph subset contains path data for every selected topic', () => {
  assert.equal(Object.keys(ONTOLOGY_TOPIC_GLYPHS).length,42);
  for(const paths of Object.values(ONTOLOGY_TOPIC_GLYPHS)) {
    assert.ok(paths.length>0);
    for(const path of paths) assert.match(path,/^[Mm]/);
  }
});
