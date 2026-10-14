import { getApiUrl } from '@/lib/config';

/** HTTPS or Nexus API path (stored in GeoJSON / env config). */
export function mapsPinImageUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (trimmed.startsWith('/api/') && !trimmed.startsWith('//')) return trimmed;
  // Object URL of a logo loaded with the member's token (stored feed logos).
  if (/^blob:https?:\/\//.test(trimmed)) return trimmed;
  try {
    return new URL(trimmed).protocol === 'https:' ? trimmed : undefined;
  } catch {
    return undefined;
  }
}

/**
 * URL for `<img>` and Leaflet HTML. Nexus web does not proxy every `/api/*`
 * route (e.g. organization logos on the ABI API), so resolve paths there.
 */
export function resolveMapsPinImageUrl(value: unknown): string | undefined {
  const path = mapsPinImageUrl(value);
  if (!path) return undefined;
  if (path.startsWith('https://') || path.startsWith('blob:')) return path;
  if (path.startsWith('/api/')) {
    if (typeof window === 'undefined') return path;
    return `${getApiUrl().replace(/\/$/, '')}${path}`;
  }
  return undefined;
}
