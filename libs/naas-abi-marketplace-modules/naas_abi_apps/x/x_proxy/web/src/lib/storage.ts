/**
 * Browser storage that survives the sandbox.
 *
 * The app runs in an opaque origin (Nexus serves remote modules' apps
 * sandboxed): `localStorage`, `sessionStorage` and `document.cookie` throw
 * there. Each read and write is guarded, and a value kept in memory stands in
 * when the storage is not usable, so the app keeps its state for as long as
 * the page lives (a reload starts again from the defaults).
 */

type Kind = "local" | "session";

const memory: Record<Kind, Map<string, string>> = {
  local: new Map(),
  session: new Map(),
};

function storage(kind: Kind): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    // Reading the property itself throws in an opaque origin.
    const store = kind === "local" ? window.localStorage : window.sessionStorage;
    return store ?? null;
  } catch {
    return null;
  }
}

export function readStored(kind: Kind, key: string): string | null {
  const store = storage(kind);
  if (store) {
    try {
      const value = store.getItem(key);
      if (value !== null) return value;
    } catch {
      // Blocked storage: the in-memory copy below.
    }
  }
  return memory[kind].get(key) ?? null;
}

export function writeStored(kind: Kind, key: string, value: string): void {
  memory[kind].set(key, value);
  const store = storage(kind);
  if (!store) return;
  try {
    store.setItem(key, value);
  } catch {
    // Blocked or full storage: the in-memory copy above keeps the value.
  }
}
