import { create } from 'zustand';
import { synchronizePermissionContext, usePermissionCache } from '@/lib/permission-cache';

/** A refusal (401/403/404) is kept briefly: access can be granted soon after. */
export const RESOURCE_DENIED_TTL_MS = 15_000;
const MAX_ENTRIES = 64;
const MAX_ENTRY_BYTES = 1024 * 1024;
const MAX_TOTAL_BYTES = 4 * 1024 * 1024;

/**
 * What a business resource read may reuse, declared once per resource rather than
 * decided by the page that happens to be open: a prefetch and a page read of the
 * same resource follow the same policy.
 */
export interface ResourcePolicy<P> {
  /** Unique; part of every key. */
  name: string;
  /** How long a successful answer is reused. */
  ttlMs: number;
  /** The parameters' part of the key. */
  key: (params: P) => string;
  /** Whether the API's settings cache (`X-Nexus-Cache`) may answer the read. */
  backendCache: boolean;
  /** Whether a successful change at this API path (no query) makes the answer for `params` stale. */
  invalidatedBy: (path: string, params: P) => boolean;
}

type Snapshot = { body: string; status: number; contentType: string };
type Entry = {
  resource: string;
  params: unknown;
  epoch: number;
  expiresAt: number;
  bytes: number;
  snapshot?: Snapshot;
  pending?: Promise<Snapshot | Response>;
};

export class ResourceSessionChanged extends Error {
  constructor() {
    super('The session changed while the resource was read.');
    this.name = 'ResourceSessionChanged';
  }
}

export interface ResourceCacheState {
  /** The session the entries belong to (the permission cache's identity); null: nothing is kept. */
  session: string | null;
  /** Bumped whenever entries are dropped wholesale, so older reads never refill them. */
  epoch: number;
  entries: Map<string, Entry>;
  bytes: number;
  /** The clock entries expire by (a test passes its own). */
  now: () => number;
  bind: (session: string | null) => void;
  clear: () => void;
  invalidate: (match: (resource: string, params: unknown) => boolean) => void;
}

const policies = new Map<string, ResourcePolicy<never>>();

export function defineResource<P>(policy: ResourcePolicy<P>): ResourcePolicy<P> {
  policies.set(policy.name, policy as unknown as ResourcePolicy<never>);
  return policy;
}

const keyOf = (policy: ResourcePolicy<never>, params: unknown) =>
  `${policy.name}\u0000${(policy.key as (p: unknown) => string)(params)}`;

const responseOf = (snapshot: Snapshot) =>
  new Response(snapshot.body, {
    status: snapshot.status,
    headers: snapshot.contentType ? { 'content-type': snapshot.contentType } : {},
  });

/** Memory only: no persist middleware, browser storage, token or authorization decision. */
export function createResourceCache(now: () => number = () => Date.now()) {
  return create<ResourceCacheState>((set, get) => ({
    session: null,
    epoch: 0,
    entries: new Map(),
    bytes: 0,
    now,
    bind: (session) => {
      if (session === get().session) return;
      set((state) => ({ session, epoch: state.epoch + 1, entries: new Map(), bytes: 0 }));
    },
    clear: () => set((state) => ({ epoch: state.epoch + 1, entries: new Map(), bytes: 0 })),
    invalidate: (match) => {
      const entries = new Map(get().entries);
      let bytes = get().bytes;
      for (const [key, entry] of entries) {
        if (!match(entry.resource, entry.params)) continue;
        entries.delete(key);
        bytes -= entry.bytes;
      }
      if (entries.size !== get().entries.size) set({ entries, bytes });
    },
  }));
}

export type ResourceCache = ReturnType<typeof createResourceCache>;

export const useResourceCache = createResourceCache();

/** The permission cache already names the session (API, user, provider, View as): follow it. */
function followSession(cache: ResourceCache) {
  const { identity, enabled } = usePermissionCache.getState();
  cache.getState().bind(enabled ? identity : null);
}
usePermissionCache.subscribe(() => followSession(useResourceCache));
followSession(useResourceCache);

function sessionOf(cache: ResourceCache) {
  if (cache === useResourceCache) {
    synchronizePermissionContext();
    followSession(cache);
  }
  const { session, epoch } = cache.getState();
  return { session, epoch };
}

function store(cache: ResourceCache, key: string, entry: Entry) {
  const state = cache.getState();
  const entries = new Map(state.entries);
  let bytes = state.bytes - (entries.get(key)?.bytes ?? 0);
  entries.delete(key);
  entries.set(key, entry);
  bytes += entry.bytes;
  // Least recently used first; an entry still in flight is never evicted.
  for (const [oldKey, old] of entries) {
    if (entries.size <= MAX_ENTRIES && bytes <= MAX_TOTAL_BYTES) break;
    if (old.pending || oldKey === key) continue;
    entries.delete(oldKey);
    bytes -= old.bytes;
  }
  cache.setState({ entries, bytes });
}

function drop(cache: ResourceCache, key: string, entry: Entry) {
  const state = cache.getState();
  if (state.entries.get(key) !== entry) return;
  const entries = new Map(state.entries);
  entries.delete(key);
  cache.setState({ entries, bytes: state.bytes - entry.bytes });
}

export interface ReadOptions {
  /** Skip a settled answer (Reload, a page's own refresh); a read in flight is still joined. */
  force?: boolean;
  cache?: ResourceCache;
}

/**
 * Read a resource through the cache: a fresh answer is served from memory, callers at
 * the same time share one request, and an answer that belongs to an older session is
 * never delivered (`ResourceSessionChanged`). An answer invalidated while in flight is
 * delivered to its callers but not kept. Failures and non-JSON answers are never kept.
 */
export function readResource<P>(
  policy: ResourcePolicy<P>,
  params: P,
  load: () => Promise<Response>,
  { force = false, cache = useResourceCache }: ReadOptions = {},
): Promise<Response> {
  const started = sessionOf(cache);
  const key = keyOf(policy as unknown as ResourcePolicy<never>, params);
  const current = () => {
    const now = sessionOf(cache);
    if (now.session !== started.session || now.epoch !== started.epoch) throw new ResourceSessionChanged();
  };
  // An unknown or changing session keeps nothing, and its answers are checked all the same.
  if (started.session === null) {
    return load().then((response) => {
      current();
      return response;
    });
  }

  const now = cache.getState().now;
  const previous = cache.getState().entries.get(key);
  const deliver = (value: Snapshot | Response) => {
    current();
    return value instanceof Response ? value.clone() : responseOf(value);
  };
  if (previous?.pending) return previous.pending.then(deliver);
  if (!force && previous?.snapshot && previous.expiresAt > now()) {
    store(cache, key, previous);
    return Promise.resolve(previous.snapshot).then(deliver);
  }

  const entry: Entry = { resource: policy.name, params, epoch: started.epoch, expiresAt: 0, bytes: 0 };
  const pending = load().then(async (response): Promise<Snapshot | Response> => {
    current();
    const contentType = response.headers.get('content-type') ?? '';
    const keep = response.ok || [401, 403, 404].includes(response.status);
    if (!keep || !contentType.startsWith('application/json')) {
      drop(cache, key, entry);
      return response;
    }
    const body = await response.text();
    current();
    const snapshot: Snapshot = { body, status: response.status, contentType };
    const bytes = body.length * 2;
    if (cache.getState().entries.get(key) !== entry || bytes > MAX_ENTRY_BYTES) {
      // Invalidated meanwhile, or too large to keep: answer the callers only.
      drop(cache, key, entry);
      return snapshot;
    }
    const ttl = response.ok ? policy.ttlMs : Math.min(policy.ttlMs, RESOURCE_DENIED_TTL_MS);
    // Settled: no longer joined as a flight, so it expires and can be evicted.
    store(cache, key, { ...entry, pending: undefined, snapshot, bytes, expiresAt: now() + ttl });
    return snapshot;
  }).catch((error: unknown) => {
    drop(cache, key, entry);
    throw error;
  });
  entry.pending = pending;
  store(cache, key, entry);
  return pending.then(deliver);
}

/** Whether a fresh answer is held for these parameters (no request is made). */
export function hasFreshResource<P>(
  policy: ResourcePolicy<P>,
  params: P,
  cache: ResourceCache = useResourceCache,
): boolean {
  if (sessionOf(cache).session === null) return false;
  const entry = cache.getState().entries.get(keyOf(policy as unknown as ResourcePolicy<never>, params));
  return !!entry?.snapshot && entry.snapshot.status < 300 && entry.expiresAt > cache.getState().now();
}

/**
 * Keep an answer obtained otherwise (a reconciliation that returns the same body as the
 * read). Ignored for another session than the one current when `epoch` was read.
 */
export function primeResource<P>(
  policy: ResourcePolicy<P>,
  params: P,
  body: string,
  epoch: number,
  cache: ResourceCache = useResourceCache,
): void {
  const { session, epoch: currentEpoch } = sessionOf(cache);
  if (session === null || epoch !== currentEpoch || body.length * 2 > MAX_ENTRY_BYTES) return;
  const key = keyOf(policy as unknown as ResourcePolicy<never>, params);
  store(cache, key, {
    resource: policy.name,
    params,
    epoch,
    bytes: body.length * 2,
    expiresAt: cache.getState().now() + policy.ttlMs,
    snapshot: { body, status: 200, contentType: 'application/json' },
  });
}

/** The epoch to hand back to `primeResource` once an answer arrives. */
export function resourceEpoch(cache: ResourceCache = useResourceCache): number {
  return sessionOf(cache).epoch;
}

export function invalidateResource<P>(
  policy: ResourcePolicy<P>,
  match: (params: P) => boolean = () => true,
  cache: ResourceCache = useResourceCache,
): void {
  cache.getState().invalidate((resource, params) => resource === policy.name && match(params as P));
}

/** After a successful change: drop every answer its resource declares stale. */
export function invalidateResourcesAfter(path: string, cache: ResourceCache = useResourceCache): void {
  cache.getState().invalidate((resource, params) => {
    const policy = policies.get(resource);
    return !policy || (policy.invalidatedBy as (p: string, q: unknown) => boolean)(path, params);
  });
}

export function clearResources(cache: ResourceCache = useResourceCache): void {
  cache.getState().clear();
}

/** `path` is under `prefix` (the path itself or a sub-path). */
export function pathUnder(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(`${prefix}/`);
}

/** The API path of a request (no query, no trailing slash), or null for another origin. */
export function apiPath(url: string, apiBase: string): string | null {
  const origin = typeof window === 'undefined' ? 'http://nexus.invalid' : window.location.origin;
  const base = new URL(apiBase || origin, origin);
  const target = new URL(url, base);
  if (target.origin !== base.origin) return null;
  return target.pathname.replace(/\/$/, '') || '/';
}
