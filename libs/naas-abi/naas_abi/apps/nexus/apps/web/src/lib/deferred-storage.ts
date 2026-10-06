import type { PersistStorage, StorageValue } from 'zustand/middleware';

// zustand `persist` + createJSONStorage stringifies and writes the whole
// partialized state on every `set()`. For big stores (agents, ontology,
// workspace conversations) that is 100+ KB of synchronous JSON.stringify +
// localStorage.setItem inside whatever triggered the set — typically a dock
// click — which then blocks the section switch. This storage keeps the latest
// state object per key and serializes it off the interaction path (coalesced,
// on idle), flushing when the page is hidden so nothing is lost.

const DEFAULT_DELAY_MS = 1000;

type Backend = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

const pending = new Map<string, { value: unknown; backend: Backend }>();
let timer: ReturnType<typeof setTimeout> | null = null;
let listening = false;

function write(name: string) {
  const entry = pending.get(name);
  if (!entry) return;
  pending.delete(name);
  try {
    entry.backend.setItem(name, JSON.stringify(entry.value));
  } catch {
    // Quota exceeded / storage unavailable: persistence is best effort.
  }
}

export function flushDeferredStorage() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  for (const name of Array.from(pending.keys())) write(name);
}

/**
 * Drop queued writes so a later flush cannot resurrect keys that are being
 * cleared (logout, "reset config"). Call before `localStorage.removeItem`.
 */
export function discardDeferredStorage(names?: readonly string[]) {
  if (!names) {
    pending.clear();
    if (timer) clearTimeout(timer);
    timer = null;
    return;
  }
  for (const name of names) pending.delete(name);
}

function listenForPageHide() {
  if (listening || typeof window === 'undefined') return;
  listening = true;
  window.addEventListener('pagehide', flushDeferredStorage);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flushDeferredStorage();
  });
}

type IdleScheduler = (cb: () => void, options?: { timeout: number }) => number;

function schedule(delayMs: number) {
  if (timer) return;
  timer = setTimeout(() => {
    timer = null;
    const idle = (globalThis as { requestIdleCallback?: IdleScheduler }).requestIdleCallback;
    if (idle) idle(flushDeferredStorage, { timeout: delayMs });
    else flushDeferredStorage();
  }, delayMs);
}

// Like createJSONStorage: no storage (SSR, tests, blocked site data) makes
// persistence a no-op instead of throwing inside every store update.
function resolve(backend: () => Backend): Backend | null {
  try {
    return backend() ?? null;
  } catch {
    return null;
  }
}

export function createDeferredStorage<S>(
  backend: () => Backend = () => localStorage,
  delayMs: number = DEFAULT_DELAY_MS,
): PersistStorage<S> {
  return {
    getItem: (name) => {
      const queued = pending.get(name);
      // Round-trip so a rehydrate sees exactly what will be stored.
      const raw = queued ? JSON.stringify(queued.value) : resolve(backend)?.getItem(name) ?? null;
      if (raw === null) return null;
      try {
        return JSON.parse(raw) as StorageValue<S>;
      } catch {
        return null;
      }
    },
    setItem: (name, value) => {
      const target = resolve(backend);
      if (!target) return;
      pending.set(name, { value, backend: target });
      listenForPageHide();
      schedule(delayMs);
    },
    removeItem: (name) => {
      pending.delete(name);
      resolve(backend)?.removeItem(name);
    },
  };
}
