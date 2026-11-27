import { create } from 'zustand';

export const PERMISSION_TTL_MS = 60_000;
export const PERMISSION_DENIED_TTL_MS = 15_000;
const ERROR_TTL_MS = 2_000;
const MAX_ENTRIES = 128;
const MAX_BODY_BYTES = 256 * 1024;

export type PermissionStatus = 'unknown' | 'pending' | 'ready' | 'denied' | 'error';
type Snapshot = { body: string; status: number; headers: [string, string][] };
type Entry = {
  status: PermissionStatus;
  expiresAt: number;
  snapshot?: Snapshot;
  error?: unknown;
  pending?: Promise<Response>;
};

export class PermissionSessionChanged extends Error {
  constructor() {
    super('The permission session changed.');
    this.name = 'PermissionSessionChanged';
  }
}

export interface PermissionCacheState {
  identity: string;
  enabled: boolean;
  generation: number;
  /** A soft revalidation: consumers keep their current navigation while asking again. */
  revision: number;
  entries: Map<string, Entry>;
  identify: (identity: string, force?: boolean, enabled?: boolean) => void;
  invalidate: () => void;
  revalidate: () => void;
  read: (key: string, load: () => Promise<Response>, options?: {
    force?: boolean;
    /** Recheck the API/session after an asynchronous request. */
    current?: () => void;
  }) => Promise<Response>;
}

const responseOf = (snapshot: Snapshot) => new Response(snapshot.body, {
  status: snapshot.status, headers: snapshot.headers,
});

/** Memory only. No persist middleware, browser storage, token, or backend authorization logic. */
export function createPermissionCache(now: () => number = Date.now, limit = MAX_ENTRIES, synchronize: () => void = () => undefined) {
  return create<PermissionCacheState>((set, get) => ({
    identity: '', enabled: false, generation: 0, revision: 0, entries: new Map(),
    identify: (identity, force = false, enabled = true) => {
      if (!force && identity === get().identity && enabled === get().enabled) return;
      set((state) => ({ identity, enabled, generation: state.generation + 1, entries: new Map() }));
    },
    invalidate: () => get().identify(get().identity, true, get().enabled),
    revalidate: () => {
      if ([...get().entries.values()].some((entry) => !entry.pending && entry.expiresAt <= now())) {
        set((state) => ({ revision: state.revision + 1 }));
      }
    },
    read: (key, load, { force = false, current = () => undefined } = {}) => {
      synchronize();
      const state = get();
      let generation = state.generation;
      const deliver = (response: Response) => {
        synchronize();
        current();
        if (get().generation !== generation) throw new PermissionSessionChanged();
        return response.clone();
      };
      const uncached = () => Promise.resolve().then(() => {
        synchronize();
        current();
        if (get().generation !== state.generation) throw new PermissionSessionChanged();
        return load();
      }).then((response) => {
        synchronize();
        current();
        if (get().generation !== state.generation) throw new PermissionSessionChanged();
        return response;
      });
      if (!state.enabled) return uncached();
      const previous = state.entries.get(key);
      // A refresh joins an already-running read; mutations invalidate its generation instead.
      if (previous?.pending) return previous.pending.then(deliver);
      if (!force && previous && previous.expiresAt > now()) {
        const entries = new Map(state.entries);
        entries.delete(key);
        entries.set(key, previous);
        set({ entries });
        return previous.snapshot ? Promise.resolve(responseOf(previous.snapshot)).then(deliver) : Promise.reject(previous.error);
      }
      const entries = new Map(state.entries);
      entries.delete(key);
      while (entries.size >= limit) {
        const oldest = [...entries].find(([, entry]) => !entry.pending)?.[0];
        // Do not grow memory without bound when every slot is in flight.
        if (oldest === undefined) return uncached();
        entries.delete(oldest);
      }
      const entry: Entry = { status: 'pending', expiresAt: 0 };
      const isCurrent = () => {
        synchronize();
        current();
        return get().generation === generation && get().entries.get(key) === entry;
      };
      const publish = (value: Entry) => {
        if (!isCurrent()) throw new PermissionSessionChanged();
        const next = new Map(get().entries);
        next.set(key, value);
        const changed = value.status !== 'error' && previous?.snapshot && value.snapshot &&
          (previous.snapshot.body !== value.snapshot.body || previous.snapshot.status !== value.snapshot.status);
        if (changed) {
          // A newly observed grant/revocation can affect other scopes too. Keep
          // this fresh answer, forget siblings, and reject their older flights.
          generation += 1;
          set({ entries: new Map([[key, value]]), generation });
        } else {
          set({ entries: next });
        }
      };
      const pending = Promise.resolve().then(() => {
        if (!isCurrent()) throw new PermissionSessionChanged();
        return load();
      }).then(async (response) => {
        if (!isCurrent()) throw new PermissionSessionChanged();
        const type = response.headers.get('content-type') ?? '';
        if (!type.startsWith('application/json') || response.headers.has('set-cookie')) {
          const next = new Map(get().entries);
          next.delete(key);
          set({ entries: next });
          return response;
        }
        const body = await response.clone().text();
        if (!isCurrent()) throw new PermissionSessionChanged();
        if (body.length * 2 > MAX_BODY_BYTES) {
          const next = new Map(get().entries);
          next.delete(key);
          set({ entries: next });
          return response;
        }
        const denied = [401, 403, 404].includes(response.status);
        const status = response.ok ? 'ready' : denied ? 'denied' : 'error';
        publish({
          status,
          expiresAt: now() + (response.ok ? PERMISSION_TTL_MS : denied ? PERMISSION_DENIED_TTL_MS : ERROR_TTL_MS),
          snapshot: { body, status: response.status, headers: [...response.headers.entries()] },
        });
        return response;
      }).catch((error: unknown) => {
        if (isCurrent()) publish({ status: 'error', expiresAt: now() + ERROR_TTL_MS, error });
        throw error;
      });
      entry.pending = pending;
      entries.set(key, entry);
      set({ entries });
      return pending.then(deliver);
    },
  }));
}

let contextReader: () => void = () => undefined;
export function configurePermissionContext(reader: () => void): void { contextReader = reader; }
export function synchronizePermissionContext(): void { contextReader(); }
export const usePermissionCache = createPermissionCache(() => Date.now(), MAX_ENTRIES, synchronizePermissionContext);
export const permissionSessionKey = () => {
  const { identity, generation } = usePermissionCache.getState();
  return JSON.stringify([identity, generation]);
};
export function usePermissionSessionKey(): string {
  return usePermissionCache((state) => JSON.stringify([state.identity, state.generation]));
}
export function usePermissionRevision(): number {
  return usePermissionCache((state) => state.revision);
}

/** Deliberately small allowlist; arbitrary API/business reads remain live. */
export function permissionReadKey(url: string, apiBase: string, options: RequestInit = {}): string | null {
  if ((options.method ?? 'GET').toUpperCase() !== 'GET' || options.cache === 'no-store') return null;
  if (Object.keys(options).some((key) => !['method', 'cache'].includes(key))) return null;
  const origin = typeof window === 'undefined' ? 'http://nexus.invalid' : window.location.origin;
  const base = new URL(apiBase || origin, origin);
  const target = new URL(url, base);
  if (target.origin !== base.origin) return null;
  const path = target.pathname.replace(/\/$/, '');
  if (path === '/api/iam/admin/access') {
    const keys = [...target.searchParams.keys()];
    if (keys.some((key) => key !== 'scope') || keys.length > 1) return null;
    const scope = target.searchParams.get('scope');
    return `http:iam:${JSON.stringify(scope === null || scope === 'abi:' ? 'abi:' : scope)}`;
  }
  if (target.search) return null;
  if (path === '/api/organizations' && options.cache === 'force-cache') return `http:${path}`;
  if (['/api/admin/me', '/api/admin/ping'].includes(path) ||
      /^\/api\/(?:analytics|(?:organizations|workspaces)\/[^/]+\/analytics)\/access$/.test(path)) return `http:${path}`;
  return null;
}

/** IAM changes can affect other principals and descendants: invalidate permissions conservatively. */
export function changesPermissions(url: string, method: string, apiBase: string): boolean {
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return false;
  const origin = typeof window === 'undefined' ? 'http://nexus.invalid' : window.location.origin;
  const base = new URL(apiBase || origin, origin);
  const target = new URL(url, base);
  if (target.origin !== base.origin) return false;
  const path = target.pathname.replace(/\/$/, '');
  if (['/api/iam/admin/simulate', '/api/iam/admin/policies/validate'].includes(path)) return false;
  return path.startsWith('/api/iam/admin/') || path.startsWith('/api/admin/users/') ||
    path === '/api/settings-cache/refresh' ||
    /^\/api\/(?:organizations|workspaces)(?:\/[^/]+)?$/.test(path) ||
    /^\/api\/(?:organizations|workspaces)\/[^/]+\/(?:members|roles|feature-access|offer|analytics)(?:\/|$)/.test(path);
}
