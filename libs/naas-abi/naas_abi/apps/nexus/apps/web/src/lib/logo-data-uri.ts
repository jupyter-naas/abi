import { getApiUrl } from '@/lib/config';

/**
 * A logo as a `data:` URI, for drawing it into the graph's SVG.
 *
 * An image the API serves is read from the API itself, with the session; any
 * other comes through `/api/image-data`, which fetches public images only.
 */
export async function logoDataUri(url: string): Promise<string | null> {
  const api = getApiUrl().replace(/\/$/, '');
  if (url.startsWith(`${api}/`)) {
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) return null;
    const type = (res.headers.get('content-type') ?? '').split(';')[0].trim().toLowerCase();
    if (!type.startsWith('image/')) return null;
    const bytes = new Uint8Array(await res.arrayBuffer());
    let binary = '';
    for (let at = 0; at < bytes.length; at += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(at, at + 0x8000));
    }
    return `data:${type};base64,${btoa(binary)}`;
  }
  const res = await fetch(`/api/image-data?url=${encodeURIComponent(url)}`);
  if (!res.ok) return null;
  const json = (await res.json()) as { dataUri?: unknown };
  return typeof json.dataUri === 'string' ? json.dataUri : null;
}
