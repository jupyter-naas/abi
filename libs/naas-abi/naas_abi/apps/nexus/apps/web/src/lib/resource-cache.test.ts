import { describe, expect, it } from 'vitest';
import {
  RESOURCE_DENIED_TTL_MS,
  ResourceSessionChanged,
  apiPath,
  createResourceCache,
  defineResource,
  hasFreshResource,
  invalidateResource,
  invalidateResourcesAfter,
  primeResource,
  readResource,
  resourceEpoch,
} from './resource-cache';

const ORG = defineResource<{ orgId: string }>({
  name: 'test-org',
  ttlMs: 60_000,
  key: ({ orgId }) => orgId,
  backendCache: false,
  invalidatedBy: (path, { orgId }) => path === `/api/organizations/${orgId}`,
});

const json = (body: unknown, status = 200) => Response.json(body, { status });

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, ko) => {
    resolve = ok;
    reject = ko;
  });
  return { promise, resolve, reject };
}

function setup(session: string | null = 'user-a') {
  let time = 1_000;
  const cache = createResourceCache(() => time);
  cache.getState().bind(session);
  const loads: string[] = [];
  const read = (orgId: string, body: unknown = { orgId }, options: { force?: boolean } = {}) =>
    readResource(ORG, { orgId }, async () => {
      loads.push(orgId);
      return json(body);
    }, { cache, ...options });
  return { cache, loads, read, advance: (ms: number) => { time += ms; } };
}

describe('readResource', () => {
  it('shares one request between callers at the same time and serves a fresh answer from memory', async () => {
    const { cache } = setup();
    const reply = deferred<Response>();
    let loads = 0;
    const load = () => ((loads += 1), reply.promise);
    const first = readResource(ORG, { orgId: 'a' }, load, { cache });
    const second = readResource(ORG, { orgId: 'a' }, load, { cache });
    reply.resolve(json({ name: 'Acme' }));
    expect(await (await first).json()).toEqual({ name: 'Acme' });
    // Each caller reads its own body.
    expect(await (await second).json()).toEqual({ name: 'Acme' });
    expect(await (await readResource(ORG, { orgId: 'a' }, load, { cache })).json()).toEqual({ name: 'Acme' });
    expect(loads).toBe(1);
  });

  it('reads again once the policy says the answer is old, and on force', async () => {
    const { read, loads, advance } = setup();
    await read('a');
    advance(59_999);
    await read('a');
    expect(loads).toEqual(['a']);
    advance(1);
    await read('a');
    expect(loads).toEqual(['a', 'a']);
    await read('a', {}, { force: true });
    expect(loads).toEqual(['a', 'a', 'a']);
  });

  it('keeps a refusal briefly, never a failure or a body that is not JSON', async () => {
    const { cache, advance } = setup();
    let loads = 0;
    const refused = () => readResource(ORG, { orgId: 'a' }, async () => ((loads += 1), json({ detail: 'no' }, 403)), { cache });
    expect((await refused()).status).toBe(403);
    expect((await refused()).status).toBe(403);
    expect(loads).toBe(1);
    advance(RESOURCE_DENIED_TTL_MS);
    await refused();
    expect(loads).toBe(2);

    let failures = 0;
    const failing = () => readResource(ORG, { orgId: 'b' }, async () => ((failures += 1), json({}, 503)), { cache });
    await failing();
    await failing();
    expect(failures).toBe(2);

    let errors = 0;
    const offline = () => readResource(ORG, { orgId: 'c' }, async () => {
      errors += 1;
      throw new TypeError('Failed to fetch');
    }, { cache });
    await expect(offline()).rejects.toThrow('Failed to fetch');
    await expect(offline()).rejects.toThrow('Failed to fetch');
    expect(errors).toBe(2);

    let texts = 0;
    const text = () => readResource(ORG, { orgId: 'd' }, async () => ((texts += 1), new Response('plain')), { cache });
    expect(await (await text()).text()).toBe('plain');
    await text();
    expect(texts).toBe(2);
  });

  it('keeps nothing while the session is unknown', async () => {
    const { read, loads } = setup(null);
    await read('a');
    await read('a');
    expect(loads).toEqual(['a', 'a']);
  });

  it('delivers, without keeping, a read begun before the session was confirmed', async () => {
    const { cache, read, loads } = setup(null);
    const reply = deferred<Response>();
    const early = readResource(ORG, { orgId: 'a' }, () => reply.promise, { cache });
    // The API confirms the session meanwhile: the read carried that session's cookie.
    cache.getState().bind('user-a');
    reply.resolve(json({ name: 'Acme' }));
    expect(await (await early).json()).toEqual({ name: 'Acme' });
    await read('a');
    expect(loads).toEqual(['a']);
  });

  it('never delivers an answer begun in another session, even after A, B, then A again', async () => {
    const { cache } = setup('user-a');
    const reply = deferred<Response>();
    const flight = readResource(ORG, { orgId: 'a' }, () => reply.promise, { cache });
    cache.getState().bind('user-b');
    cache.getState().bind('user-a');
    reply.resolve(json({ name: 'for the first A' }));
    await expect(flight).rejects.toBeInstanceOf(ResourceSessionChanged);
    expect(cache.getState().entries.size).toBe(0);

    let loads = 0;
    await readResource(ORG, { orgId: 'a' }, async () => ((loads += 1), json({})), { cache });
    expect(loads).toBe(1);
  });

  it('answers a read invalidated in flight without keeping it, and the next read asks again', async () => {
    const { cache, read, loads } = setup();
    const reply = deferred<Response>();
    const flight = readResource(ORG, { orgId: 'a' }, () => reply.promise, { cache });
    invalidateResourcesAfter('/api/organizations/a', cache);
    // A read after the change does not join the older flight.
    const after = read('a', { name: 'after' });
    reply.resolve(json({ name: 'before' }));
    expect(await (await flight).json()).toEqual({ name: 'before' });
    expect(await (await after).json()).toEqual({ name: 'after' });
    expect(loads).toEqual(['a']);
    expect(await (await read('a')).json()).toEqual({ name: 'after' });
    expect(loads).toEqual(['a']);
  });

  it('drops only what a change concerns', async () => {
    const { cache, read, loads } = setup();
    await read('a');
    await read('b');
    invalidateResourcesAfter('/api/organizations/a', cache);
    await read('a');
    await read('b');
    expect(loads).toEqual(['a', 'b', 'a']);
    invalidateResource(ORG, ({ orgId }) => orgId === 'b', cache);
    await read('b');
    expect(loads).toEqual(['a', 'b', 'a', 'b']);
  });

  it('bounds what it keeps: entries, size of one answer, least recently used first', async () => {
    const { cache, read, loads } = setup();
    await read('big', { text: 'x'.repeat(600 * 1024) });
    await read('big');
    expect(loads).toEqual(['big', 'big']);

    loads.length = 0;
    for (let i = 0; i < 64; i += 1) await read(`org-${i}`);
    await read('org-0'); // used again: kept over org-1
    await read('org-64');
    expect(cache.getState().entries.size).toBe(64);
    loads.length = 0;
    await read('org-0');
    await read('org-1');
    expect(loads).toEqual(['org-1']);
    expect(cache.getState().bytes).toBeLessThanOrEqual(4 * 1024 * 1024);
  });

  it('primes an answer obtained otherwise, but not across sessions', async () => {
    const { cache, read, loads } = setup();
    const epoch = resourceEpoch(cache);
    primeResource(ORG, { orgId: 'a' }, JSON.stringify({ name: 'primed' }), epoch, cache);
    expect(hasFreshResource(ORG, { orgId: 'a' }, cache)).toBe(true);
    expect(await (await read('a')).json()).toEqual({ name: 'primed' });
    expect(loads).toEqual([]);

    cache.getState().bind('user-b');
    primeResource(ORG, { orgId: 'b' }, '{}', epoch, cache);
    expect(hasFreshResource(ORG, { orgId: 'b' }, cache)).toBe(false);
  });
});

describe('apiPath', () => {
  it('names the API path of a request, never another origin', () => {
    expect(apiPath('/api/organizations/a/', 'http://api.test')).toBe('/api/organizations/a');
    expect(apiPath('http://api.test/api/agents/x?workspace_id=1', 'http://api.test')).toBe('/api/agents/x');
    expect(apiPath('https://elsewhere.test/api/agents', 'http://api.test')).toBeNull();
  });
});
