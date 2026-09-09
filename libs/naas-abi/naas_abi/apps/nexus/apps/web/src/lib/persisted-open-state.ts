/**
 * Open/collapsed state keyed by id (agent, deck slug, ...), persisted to
 * localStorage so it survives reloads. An in-memory cache avoids
 * re-parsing the stored blob on every render.
 */
export function createPersistedOpenState(storageKey: string) {
  const cache = new Map<string, boolean>();

  function readStoredMap(): Record<string, boolean> {
    if (typeof window === 'undefined') return {};
    try {
      const raw = window.localStorage.getItem(storageKey);
      return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
    } catch {
      return {};
    }
  }

  return {
    load(id: string): boolean {
      const cached = cache.get(id);
      if (cached !== undefined) return cached;
      const value = readStoredMap()[id] ?? false;
      cache.set(id, value);
      return value;
    },
    save(id: string, value: boolean): void {
      cache.set(id, value);
      if (typeof window === 'undefined') return;
      try {
        const map = readStoredMap();
        map[id] = value;
        window.localStorage.setItem(storageKey, JSON.stringify(map));
      } catch {
        // Best-effort persistence only.
      }
    },
  };
}
