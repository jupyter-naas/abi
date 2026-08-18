import { getApiUrl } from '@/lib/config';

/** Engine default API port when global_config.public_api_host is unset. */
const ENGINE_DEFAULT_API_PORTS = new Set(['9879']);

/**
 * Resolve an agent/app logo for <img src>.
 *
 * Relative paths are prefixed with the Nexus API the browser already uses.
 * Absolute URLs that still point at the engine default (loopback:9879) are
 * rewritten to that same API so `abi dev up` (allocated ports) does not 404.
 */
export function getLogoUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  const api = getApiUrl().replace(/\/$/, '');

  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      const parsed = new URL(url);
      const loopback =
        parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1';
      if (loopback && ENGINE_DEFAULT_API_PORTS.has(parsed.port)) {
        return `${api}${parsed.pathname}${parsed.search}`;
      }
    } catch {
      return url;
    }
    return url;
  }

  return url.startsWith('/') ? `${api}${url}` : `${api}/${url}`;
}
