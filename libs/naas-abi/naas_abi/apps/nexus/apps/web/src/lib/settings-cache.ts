/**
 * Settings pages read their API data through the backend's 24h settings cache.
 * The backend only caches GET requests that carry this header, and the web app only
 * sends it from settings pages, so the rest of the app always reads live data.
 */
export const SETTINGS_CACHE_HEADER = 'X-Nexus-Cache';
export const SETTINGS_CACHE_REFRESH_PATH = '/api/settings-cache/refresh';

const SETTINGS_ROUTE = /^\/(?:workspace|organizations)\/[^/]+\/settings(?:\/|$)/;

export function isSettingsRoute(pathname: string): boolean {
  return SETTINGS_ROUTE.test(pathname);
}

/** True when a request should opt in to the settings cache. */
export function shouldUseSettingsCache(pathname: string, method: string | undefined): boolean {
  return (method ?? 'GET').toUpperCase() === 'GET' && isSettingsRoute(pathname);
}

// Flips to false when the API rejects the header (e.g. an API older than the web app,
// whose CORS rules do not allow it). Settings pages then read live data for the session.
let supported = true;

export function settingsCacheSupported(): boolean {
  return supported;
}

export function resetSettingsCacheSupport(): void {
  supported = true;
}

/**
 * Send a request with the cache header when wanted; if it fails at the network level
 * (a CORS preflight rejection surfaces as "Failed to fetch"), retry once without it and
 * stop sending the header for the rest of the session.
 */
export async function fetchWithSettingsCacheFallback(
  wantCache: boolean,
  send: (useCache: boolean) => Promise<Response>
): Promise<Response> {
  const useCache = wantCache && supported;
  if (!useCache) return send(false);
  try {
    return await send(true);
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    supported = false;
    console.warn('Settings cache header rejected by the API; reading live data instead.');
    return send(false);
  }
}
