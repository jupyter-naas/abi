import { fetchMapsFeedPins, type MapsFeedResult } from './maps-feed';

/**
 * One load per layer object, shared by everything that needs it: the map, the
 * sidebar pin counts, the Settings type picker, and remounts while a request is
 * in flight. Kept for a minute (data changes only when it is published);
 * failures are not kept. A caller's abort never cancels the shared request.
 */
const TTL_MS = 60_000;
const TIMEOUT_MS = 60_000;

interface Entry {
  at: number;
  promise: Promise<MapsFeedResult>;
}

const loads = new Map<string, Entry>();

function abortable<T>(promise: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
    signal.addEventListener('abort', onAbort, { once: true });
    promise.then(
      (value) => {
        signal.removeEventListener('abort', onAbort);
        resolve(value);
      },
      (error: unknown) => {
        signal.removeEventListener('abort', onAbort);
        reject(error);
      },
    );
  });
}

/** `key` names what is loaded (default: the URL); layers sharing an object share its key. */
export function sharedFeedLoad(
  url: string,
  headers?: HeadersInit,
  signal?: AbortSignal,
  key: string = url,
): Promise<MapsFeedResult> {
  let entry = loads.get(key);
  if (!entry || Date.now() - entry.at > TTL_MS) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new Error('Map feed request timed out.')), TIMEOUT_MS);
    // Revalidate with the ETag instead of downloading an unchanged object again.
    const promise = fetchMapsFeedPins(url, controller.signal, headers, 'no-cache').finally(() =>
      clearTimeout(timer),
    );
    const created: Entry = { at: Date.now(), promise };
    entry = created;
    loads.set(key, created);
    promise.catch(() => {
      if (loads.get(key) === created) loads.delete(key);
    });
  }
  return abortable(entry.promise, signal);
}

export function clearSharedFeedLoads(): void {
  loads.clear();
}
