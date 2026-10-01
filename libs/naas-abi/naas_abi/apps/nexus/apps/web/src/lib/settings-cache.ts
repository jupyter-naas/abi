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
