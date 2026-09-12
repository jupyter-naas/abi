import { useEffect } from 'react';

const RECOVERY_INTERVAL_MS = 4_000;

/** Network / gateway blips. A 404 or validation error is not retried. */
export function isTransientOfficeListError(error: unknown): boolean {
  const message = (error instanceof Error ? error.message : String(error || '')).toLowerCase();
  if (!message) return false;
  return (
    message.includes('failed to fetch') ||
    message.includes('network') ||
    message.includes('abort') ||
    message.includes('timeout') ||
    message.includes('failed (5') ||
    /\b429\b/.test(message) ||
    /\b502\b/.test(message) ||
    /\b503\b/.test(message) ||
    /\b504\b/.test(message)
  );
}

export function isRetryableOfficeListStatus(status: number): boolean {
  return status === 429 || status >= 500;
}

export async function withOfficeListRetry<T>(
  run: () => Promise<T>,
  opts?: { attempts?: number; delayMs?: number },
): Promise<T> {
  const attempts = opts?.attempts ?? 4;
  const delayMs = opts?.delayMs ?? 350;
  let last: unknown;
  for (let i = 0; i < attempts; i += 1) {
    try {
      return await run();
    } catch (error) {
      last = error;
      if (i === attempts - 1 || !isTransientOfficeListError(error)) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs * (i + 1)));
    }
  }
  throw last;
}

/** After the first paint failed, retry when the tab is usable again. */
export function useOfficeListRecovery(
  load: (opts?: { quiet?: boolean }) => void | Promise<void>,
  error: string | null,
): void {
  useEffect(() => {
    if (!error || !isTransientOfficeListError(error)) return;
    const retry = () => {
      void load({ quiet: true });
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') retry();
    };
    window.addEventListener('focus', retry);
    window.addEventListener('online', retry);
    document.addEventListener('visibilitychange', onVisible);
    const interval = setInterval(retry, RECOVERY_INTERVAL_MS);
    return () => {
      window.removeEventListener('focus', retry);
      window.removeEventListener('online', retry);
      document.removeEventListener('visibilitychange', onVisible);
      clearInterval(interval);
    };
  }, [error, load]);
}
