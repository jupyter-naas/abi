import assert from 'node:assert/strict';
import { test } from 'node:test';
import { GraphReadCache } from './graph-request-cache';

test('recent reads expire and stay separated by workspace/filter/page keys', () => {
  let now = 0;
  const cache = new GraphReadCache(4, 30, () => now);
  const a = JSON.stringify(['alice', 'ws-a', 'urn:g', 'urn:Person', 0]);
  const b = JSON.stringify(['alice', 'ws-b', 'urn:g', 'urn:Person', 0]);
  cache.set(a, { uri: 'urn:visible' }, cache.generation);
  assert.deepEqual(cache.get(a), { uri: 'urn:visible' });
  assert.equal(cache.get(b), undefined);
  now = 30;
  assert.equal(cache.get(a), undefined);
});

test('refresh/logout invalidation rejects late results from prior requests', () => {
  const cache = new GraphReadCache();
  const prior = cache.generation;
  cache.set('old', 'visible', prior);
  cache.clear();
  cache.set('late', 'old response', prior);
  assert.equal(cache.get('old'), undefined);
  assert.equal(cache.get('late'), undefined);
  cache.set('new', 'current response', cache.generation);
  assert.equal(cache.get('new'), 'current response');
});

test('bounded cache evicts least recently used pages and supports explicit retry', () => {
  const cache = new GraphReadCache(2);
  for (const key of ['a', 'b']) cache.set(key, key, cache.generation);
  cache.get('a');
  cache.set('c', 'c', cache.generation);
  assert.equal(cache.get('b'), undefined);
  assert.equal(cache.get('a'), 'a');
  cache.delete('a');
  assert.equal(cache.get('a'), undefined);
});
