import { getApiUrl } from '@/lib/config';

/**
 * Append Nexus JWT to /app-html/ iframe URLs on the API origin so embedded
 * private app-html embeds can authenticate via ?access_token=.
 */
export function appendAccessTokenToEmbedUrl(url: string, token: string | null): string {
  if (!token) return url;

  try {
    const parsed = new URL(url, typeof window !== 'undefined' ? window.location.href : undefined);
    const apiOrigin = new URL(getApiUrl()).origin;

    if (parsed.origin !== apiOrigin) return url;
    if (!parsed.pathname.startsWith('/app-html/')) return url;

    parsed.searchParams.set('access_token', token);
    return parsed.toString();
  } catch {
    return url;
  }
}
