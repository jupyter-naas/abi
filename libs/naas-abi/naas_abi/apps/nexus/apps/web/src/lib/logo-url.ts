import { getApiUrl } from '@/lib/config';

function isLoopback(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1';
}

/**
 * Resolve an agent/app logo for <img src>.
 *
 * Relative paths are prefixed with the Nexus API the browser already uses.
 * Absolute loopback URLs whose port is not that API's port are rewritten so
 * a stale config port does not 404.
 */
export function getLogoUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  const api = getApiUrl().replace(/\/$/, '');

  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      const parsed = new URL(url);
      const apiOrigin = new URL(api);
      const staleLoopback =
        isLoopback(parsed.hostname) &&
        isLoopback(apiOrigin.hostname) &&
        parsed.port !== apiOrigin.port;
      if (staleLoopback) {
        return `${api}${parsed.pathname}${parsed.search}`;
      }
    } catch {
      return url;
    }
    return url;
  }

  return url.startsWith('/') ? `${api}${url}` : `${api}/${url}`;
}
