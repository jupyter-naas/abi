/**
 * Bundled Nexus apps are served from /app-html/ on the API (proxied
 * same-origin via Caddy). Access requires a real credential — never the
 * shared ABI_API_KEY in the browser:
 *   - logged-in session: mint a scoped JWT via POST /apps/access-token
 *   - email share links: include ``?token=<scoped-jwt>``
 *   - follow-up requests: HttpOnly ``abi_app_html_token`` cookie
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

/**
 * Path lock for scoped ``app-html`` JWTs, e.g. ``/app-html/report/counter_uas/``.
 */
export function appHtmlPathPrefix(url: string): string | null {
  const path = toAppHtmlPath(url);
  if (!path) return null;
  const pathname = path.split('?')[0].split('#')[0];
  const parts = pathname.split('/').filter(Boolean);
  // app-html / <module> / <app> / …
  if (parts.length < 3 || parts[0] !== 'app-html') {
    return '/app-html/';
  }
  return `/${parts[0]}/${parts[1]}/${parts[2]}/`;
}

/** Attach ``?token=`` (preserving existing query) for same-origin app HTML. */
export function withAppHtmlAccessToken(url: string, token: string): string {
  if (!url || !token) return url;
  const path = toAppHtmlPath(url) ?? url;
  const hashIndex = path.indexOf('#');
  const withoutHash = hashIndex >= 0 ? path.slice(0, hashIndex) : path;
  const hash = hashIndex >= 0 ? path.slice(hashIndex) : '';
  const join = withoutHash.includes('?') ? '&' : '?';
  return `${withoutHash}${join}token=${encodeURIComponent(token)}${hash}`;
}

/**
 * Resolve a catalog app URL for iframe embedding (same-origin path).
 * Callers must append a scoped access token before loading.
 */
export function resolveAppEmbedUrl(url: string): string {
  if (!url) return url;

  const path = toAppHtmlPath(url);
  if (!path) return url;

  return path;
}

/**
 * Same-origin path for opening bundled apps in a new tab.
 * Callers must append a scoped access token before navigating.
 */
export function resolveAppExternalUrl(url: string): string {
  if (!url) return url;
  const path = toAppHtmlPath(url);
  if (path) {
    return path;
  }
  return url;
}

/** Hostname used as the Pages SSO audience (must match the portal host). */
export function pagesSsoAudience(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null;
    return parsed.hostname.toLowerCase() || null;
  } catch {
    return null;
  }
}

/** Attach ``?sso=`` for a Cloudflare Pages portal handshake. */
export function withPagesSsoToken(url: string, token: string): string {
  if (!url || !token) return url;
  const hashIndex = url.indexOf('#');
  const withoutHash = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
  const hash = hashIndex >= 0 ? url.slice(hashIndex) : '';
  const join = withoutHash.includes('?') ? '&' : '?';
  return `${withoutHash}${join}sso=${encodeURIComponent(token)}${hash}`;
}
