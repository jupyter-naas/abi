/**
 * Save bookkeeping for the Documents and Slides editors.
 *
 * Every edit bumps a revision; a save captures (content, revision) and only
 * acknowledges that revision, so edits made while a request is in flight stay
 * dirty. Saves are serialized: triggers during a save coalesce into one
 * follow-up save of the newest content. After `dispose()` (document/deck
 * switch, unmount) results are reported as `stale` and must not touch the UI.
 */

export type OfficeSaveOutcome<T> =
  | { status: 'saved'; result: T; dirty: boolean }
  | { status: 'failed'; error: unknown }
  | { status: 'clean' }
  | { status: 'stale' };

export interface OfficeSaveQueue<T> {
  /** Local edit: newer than anything persisted. */
  edit(content: string): void;
  /** Content known to match the server (load, server-side mutation). */
  load(content: string): void;
  isDirty(): boolean;
  isSaving(): boolean;
  save(): Promise<OfficeSaveOutcome<T>>;
  dispose(): void;
}

export function createOfficeSaveQueue<T>(
  write: (content: string) => Promise<T>,
): OfficeSaveQueue<T> {
  let content = '';
  let revision = 0;
  let persisted = 0;
  let disposed = false;
  let running: Promise<OfficeSaveOutcome<T>> | null = null;
  let queued: Promise<OfficeSaveOutcome<T>> | null = null;

  const isDirty = () => revision !== persisted;

  const start = (): Promise<OfficeSaveOutcome<T>> => {
    if (disposed) return Promise.resolve({ status: 'stale' });
    if (!isDirty() || !content) return Promise.resolve({ status: 'clean' });
    const captured = revision;
    const snapshot = content;
    const run: Promise<OfficeSaveOutcome<T>> = Promise.resolve()
      .then(() => write(snapshot))
      .then(
        (result): OfficeSaveOutcome<T> => {
          if (disposed) return { status: 'stale' };
          // A load() during the request may already have moved `persisted` past us.
          if (captured > persisted) persisted = captured;
          return { status: 'saved', result, dirty: isDirty() };
        },
        (error): OfficeSaveOutcome<T> => (disposed ? { status: 'stale' } : { status: 'failed', error }),
      )
      .finally(() => {
        if (running === run) running = null;
      });
    running = run;
    return run;
  };

  return {
    edit(next) {
      content = next;
      revision += 1;
    },
    load(next) {
      content = next;
      revision += 1;
      persisted = revision;
    },
    isDirty,
    isSaving: () => running !== null || queued !== null,
    save() {
      if (disposed) return Promise.resolve({ status: 'stale' });
      if (!running) return start();
      if (!queued) {
        const follow = running.then(() => {
          queued = null;
          return start();
        });
        queued = follow;
      }
      return queued;
    },
    dispose() {
      disposed = true;
    },
  };
}
