export const GOOGLE_MAPS_KEY_NAMES = [
  'GOOGLE_PLACES_API_KEY',
  'GOOGLE_MAPS_API_KEY',
  'MAPS_API_KEY',
  'GOOGLE_API_KEY',
] as const;

export type GoogleMapsKeyName = (typeof GOOGLE_MAPS_KEY_NAMES)[number];

const PLACEHOLDER_KEYS = new Set([
  '',
  'your-api-key',
  'your_api_key',
  'changeme',
  'replace_me',
  'xxx',
  'demo',
]);

export function resolveGoogleMapsApiKey(
  env: NodeJS.ProcessEnv = process.env,
): { key: string; name: GoogleMapsKeyName } | null {
  for (const name of GOOGLE_MAPS_KEY_NAMES) {
    const key = (env[name] ?? '').trim();
    if (!key || PLACEHOLDER_KEYS.has(key.toLowerCase())) continue;
    if (key.length < 16) continue;
    return { key, name };
  }
  return null;
}
