import { getApiUrl } from '@/lib/config';

/**
 * Bundled Nexus apps are served from /app-html/ on the API. The web app
 * proxies that path (Caddy + Route Handler) so iframes can load same-origin.
 */

export function isBundledAppHtmlUrl(url: string): boolean {
  if (!url) return false;
  if (url.startsWith('/app-html/')) return true;
  try {
    return new URL(url).pathname.startsWith('/app-html/');
  } catch {
    return false;
  }
}

function toAppHtmlPath(url: string): string | null {
  if (url.startsWith('/app-html/')) return url;
  try {
    const parsed = new URL(url);
    if (parsed.pathname.startsWith('/app-html/')) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    // Not an absolute URL.
  }
  return null;
}

/** True when the browser is on a host that proxies /app-html/ (Caddy or route handler). */
function sameOriginAppProxyAvailable(): boolean {
  if (typeof window === 'undefined') return true;
  const { hostname, port } = window.location;
  // Direct Next.js port — proxy is only available after a web rebuild with the route handler.
  if (hostname === 'localhost' && port === '3042') return false;
  return true;
}

/**
 * Resolve a catalog app URL for iframe embedding.
 *
 * Uses same-origin ``/app-html/…`` when the web host proxies that path; otherwise
 * falls back to the API host (cross-origin, allowed via frame-ancestors).
 */
export function resolveAppEmbedUrl(url: string): string {
  if (!url) return url;

  const path = toAppHtmlPath(url);
  if (!path) return url;

  if (sameOriginAppProxyAvailable()) {
    return path;
  }

  return `${getApiUrl().replace(/\/$/, '')}${path}`;
}

/** Absolute API URL for opening bundled apps in a new browser tab. */
export function resolveAppExternalUrl(url: string): string {
  if (!url) return url;
  const path = toAppHtmlPath(url);
  if (path) {
    return `${getApiUrl().replace(/\/$/, '')}${path}`;
  }
  return url;
}
