/** Polling for the System app's live pages (jobs, agent runs, failures). */
import { useEffect, useRef } from 'react';

/** What a poll does: return its request's promise so the next one waits for it. */
export type Poll = (signal: AbortSignal) => Promise<unknown> | void;

/**
 * Calls ``fn`` now, then again ``ms`` after each call settles, while ``enabled``.
 * A tick while the page is hidden is skipped. The next call never starts before
 * the previous one has answered, so a slow server is not sent more requests than
 * it answers. ``signal`` is aborted on unmount and when ``deps`` change: pass it
 * to the request, and ignore a result that arrives after it was aborted.
 */
export function usePoll(fn: Poll, ms: number, enabled: boolean, deps: unknown[]) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer: number | undefined;
    const schedule = () => {
      if (!controller.signal.aborted) timer = window.setTimeout(tick, ms);
    };
    const call = () => {
      let pending: Promise<unknown> | void;
      try {
        pending = saved.current(controller.signal);
      } catch {
        pending = undefined;
      }
      // A failed poll is the caller's to report; polling goes on.
      void Promise.resolve(pending).catch(() => undefined).finally(schedule);
    };
    const tick = () => {
      timer = undefined;
      if (document.hidden) schedule();
      else call();
    };
    call();
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, enabled, ...deps]);
}
