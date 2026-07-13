/**
 * Browser storage with graceful degradation.
 *
 * Some environments block localStorage (strict privacy, enterprise policy,
 * Safari ITP). Auth must still work for the current tab via sessionStorage
 * or an in-memory fallback.
 */

export type SafeStorage = {
  getItem: (name: string) => string | null;
  setItem: (name: string, value: string) => void;
  removeItem: (name: string) => void;
  /** Which backend is active; useful for diagnostics. */
  backend: 'localStorage' | 'sessionStorage' | 'memory';
};

const memoryStore = new Map<string, string>();

function canUseStorage(storage: Storage | undefined): storage is Storage {
  if (!storage) return false;
  try {
    const probeKey = '__nexus_storage_probe__';
    storage.setItem(probeKey, '1');
    storage.removeItem(probeKey);
    return true;
  } catch {
    return false;
  }
}

function wrapStorage(storage: Storage, backend: SafeStorage['backend']): SafeStorage {
  return {
    backend,
    getItem: (name) => {
      try {
        return storage.getItem(name);
      } catch {
        return null;
      }
    },
    setItem: (name, value) => {
      try {
        storage.setItem(name, value);
      } catch {
        // Quota exceeded or storage blocked — caller may fall back elsewhere.
      }
    },
    removeItem: (name) => {
      try {
        storage.removeItem(name);
      } catch {
        // ignore
      }
    },
  };
}

function createMemoryStorage(): SafeStorage {
  return {
    backend: 'memory',
    getItem: (name) => memoryStore.get(name) ?? null,
    setItem: (name, value) => {
      memoryStore.set(name, value);
    },
    removeItem: (name) => {
      memoryStore.delete(name);
    },
  };
}

let cachedStorage: SafeStorage | null = null;

/** Resolve the best available storage backend for this browser context. */
export function getSafeStorage(): SafeStorage {
  if (cachedStorage) return cachedStorage;

  if (typeof window !== 'undefined') {
    if (canUseStorage(window.localStorage)) {
      cachedStorage = wrapStorage(window.localStorage, 'localStorage');
      return cachedStorage;
    }
    if (canUseStorage(window.sessionStorage)) {
      cachedStorage = wrapStorage(window.sessionStorage, 'sessionStorage');
      return cachedStorage;
    }
  }

  cachedStorage = createMemoryStorage();
  return cachedStorage;
}

/** Reset cached backend (tests only). */
export function resetSafeStorageForTests(): void {
  cachedStorage = null;
  memoryStore.clear();
}
