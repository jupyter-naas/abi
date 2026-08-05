import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

export interface GitHubConnectStatus {
  module_installed: boolean;
  connected: boolean;
  oauth_available: boolean;
}

export interface GitHubDeviceStart {
  session_id: string;
  user_code: string;
  verification_uri: string;
  interval: number;
  expires_in: number;
}

export interface GitHubDevicePoll {
  status: 'pending' | 'complete' | 'error' | 'expired';
  connected: boolean;
  interval?: number;
  github_login?: string | null;
  restart_required?: boolean;
  message?: string | null;
  detail?: string | null;
}

const apiBase = () => getApiUrl();

export async function fetchGitHubConnectStatus(): Promise<GitHubConnectStatus> {
  const response = await authFetch(`${apiBase()}/api/integrations/github/status`);
  if (!response.ok) {
    throw new Error('Failed to load GitHub connection status');
  }
  return response.json();
}

export async function startGitHubDeviceFlow(): Promise<GitHubDeviceStart> {
  const response = await authFetch(`${apiBase()}/api/integrations/github/device/start`, {
    method: 'POST',
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail || 'Failed to start GitHub authorization');
  }
  return body;
}

export async function pollGitHubDeviceFlow(sessionId: string): Promise<GitHubDevicePoll> {
  const response = await authFetch(
    `${apiBase()}/api/integrations/github/device/poll/${encodeURIComponent(sessionId)}`,
    { method: 'POST' },
  );
  if (!response.ok) {
    throw new Error('Failed to poll GitHub authorization');
  }
  return response.json();
}

export async function saveGitHubPersonalAccessToken(token: string): Promise<{
  connected: boolean;
  github_login?: string | null;
  restart_required?: boolean;
  message?: string;
}> {
  const response = await authFetch(`${apiBase()}/api/integrations/github/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail || 'Failed to save GitHub token');
  }
  return body;
}

export async function waitForGitHubDeviceAuth(
  sessionId: string,
  intervalSeconds: number,
  options?: { timeoutMs?: number },
): Promise<GitHubDevicePoll> {
  const timeoutMs = options?.timeoutMs ?? 900_000;
  const deadline = Date.now() + timeoutMs;
  let waitMs = Math.max(intervalSeconds, 3) * 1000;

  while (Date.now() < deadline) {
    const result = await pollGitHubDeviceFlow(sessionId);
    if (result.status === 'complete') {
      return result;
    }
    if (result.status === 'error' || result.status === 'expired') {
      return result;
    }
    if (result.interval) {
      waitMs = Math.max(result.interval, 3) * 1000;
    }
    await new Promise((resolve) => setTimeout(resolve, waitMs));
  }
  return { status: 'expired', connected: false, detail: 'GitHub authorization timed out' };
}
