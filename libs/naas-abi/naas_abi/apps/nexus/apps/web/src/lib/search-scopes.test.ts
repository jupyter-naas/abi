import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  allowedWebEngines, availableScopes, FEATURE_SCOPES, isScopeOn, matchScore, rankItems, RESERVED_SCOPE_IDS, scopeGroups, WEB_SCOPE_DEF,
} from './search-scopes';
import { blankTopic } from './search-topics';

test('scopes follow the workspace features and the enabled topics', () => {
  const topics = [{ ...blankTopic('person'), plural_label: 'People' }, { ...blankTopic('org'), enabled: false }];
  const scopes = availableScopes(topics, feature => feature !== 'maps');
  const ids = scopes.map(s => s.id);
  assert.equal(ids[0], 'person');
  assert.ok(!ids.includes('org'));
  assert.ok(!ids.includes('maps'));
  assert.ok(ids.includes('files'));
  assert.equal(ids.at(-1), 'web');
  assert.deepEqual(scopeGroups(scopes).map(g => g.id), ['topic', 'feature', 'web']);
});

test('web is off until switched on; everything else is on until switched off', () => {
  assert.equal(isScopeOn(WEB_SCOPE_DEF, {}), false);
  assert.equal(isScopeOn(WEB_SCOPE_DEF, { web: true }), true);
  assert.equal(isScopeOn(FEATURE_SCOPES[0]!, {}), true);
  assert.equal(isScopeOn(FEATURE_SCOPES[0]!, { [FEATURE_SCOPES[0]!.id]: false }), false);
});

test('feature ids are reserved so a topic cannot shadow them', () => {
  for (const id of ['all', 'web', 'files', 'chat', 'ontology']) assert.ok(RESERVED_SCOPE_IDS.includes(id));
});

test('matching ignores case and accents and needs every word', () => {
  assert.equal(matchScore('', 'anything'), 1);
  assert.equal(matchScore('defense', 'Paris La Défense'), 1);
  assert.equal(matchScore('paris', 'Paris La Défense'), 2);
  assert.equal(matchScore('report', 'Report'), 3);
  assert.equal(matchScore('quarterly sales', 'Q3 report', 'quarterly figures'), 0);
  assert.equal(matchScore('quarterly report', 'Q3 report', 'quarterly figures'), 1);
});

test('ranking puts exact and prefix matches first and reports more', () => {
  const items = ['Data platform', 'Data', 'Big data', 'Other'];
  const ranked = rankItems(items, 'data', item => [item], 2);
  assert.deepEqual(ranked.items, ['Data', 'Data platform']);
  assert.equal(ranked.hasMore, true);
});

test('features and engines switched off for the workspace are not offered', () => {
  const ids = (disabled: string[]) => availableScopes([], () => true, disabled).map(s => s.id);
  assert.ok(!ids(['files']).includes('files'));
  assert.ok(ids(['web.wikipedia']).includes('web'));
  assert.ok(!ids(['web.wikipedia', 'web.duckduckgo']).includes('web'));
  assert.deepEqual(allowedWebEngines(['web.duckduckgo']), ['wikipedia']);
});
