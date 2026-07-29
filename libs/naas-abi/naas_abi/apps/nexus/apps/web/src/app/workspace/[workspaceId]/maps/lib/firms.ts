/**
 * NASA FIRMS MAP_KEY helpers.
 *
 * FIRMS WMS requires a free MAP_KEY in the path:
 *   https://firms.modaps.eosdis.nasa.gov/mapserver/wms/fires/<MAP_KEY>/
 * Hitting the path without a real key returns error tiles that cover the map.
 */

const PLACEHOLDER_KEYS = new Set([
  '',
  'map_key',
  'yourmapkey',
  'your_map_key',
  'xxx',
  'demo',
  'changeme',
  'replace_me',
  'insert_map_key_here',
]);

/** Reject empty, literal "MAP_KEY", and common placeholders. */
export function resolveFirmsMapKey(raw?: string | null): string | null {
  const key = (raw ?? '').trim();
  if (!key) return null;
  if (key === 'MAP_KEY') return null;
  if (PLACEHOLDER_KEYS.has(key.toLowerCase())) return null;
  // FIRMS keys are alphanumeric; reject paths / query injection.
  if (!/^[A-Za-z0-9]+$/.test(key)) return null;
  return key;
}

/** Full FIRMS fires WMS base URL, or null when no usable key. */
export function getFirmsWmsUrl(mapKey?: string | null): string | null {
  const key = resolveFirmsMapKey(mapKey);
  if (!key) return null;
  return `https://firms.modaps.eosdis.nasa.gov/mapserver/wms/fires/${key}/`;
}
