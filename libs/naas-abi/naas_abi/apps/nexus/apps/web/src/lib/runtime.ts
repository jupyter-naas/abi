/** ABI runtime control — Restart OS. */

import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

export interface OsStatus {
  dev_runtime_available: boolean;
  restarting: boolean;
  requested_at: number | null;
}

export interface RestartOsResult {
  scheduled: boolean;
  mode: string;
  message: string;
}

export async function fetchOsStatus(): Promise<OsStatus> {
  const response = await authFetch(`${getApiUrl()}/api/runtime/os-status`);
  if (!response.ok) {
    throw new Error('Failed to read OS status');
  }
  return response.json();
}

export async function requestRestartOs(): Promise<RestartOsResult> {
  const response = await authFetch(`${getApiUrl()}/api/runtime/restart-os`, {
    method: 'POST',
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail || body?.message || 'Failed to restart OS');
  }
  return body as RestartOsResult;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Poll until the API is reachable again after an OS restart. */
export async function waitForOsOnline(options?: {
  timeoutMs?: number;
  intervalMs?: number;
}): Promise<boolean> {
  const timeoutMs = options?.timeoutMs ?? 180_000;
  const intervalMs = options?.intervalMs ?? 2_000;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    try {
      const response = await authFetch(`${getApiUrl()}/api/runtime/os-status`);
      if (response.ok) {
        const status = (await response.json()) as OsStatus;
        if (!status.restarting) {
          return true;
        }
      }
    } catch {
      /* API still down during restart */
    }
    await sleep(intervalMs);
  }
  return false;
}
