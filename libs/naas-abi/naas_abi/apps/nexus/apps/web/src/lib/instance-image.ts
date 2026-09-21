import { getLogoUrl } from '@/lib/logo-url';

export type InstanceImageSource = {
  properties?: Record<string, string | undefined | null>;
  dataProperties?: Array<{ predicate_uri: string; predicate_label?: string; value: string }>;
  relations?: Array<{ predicate_uri: string; predicate_label?: string; other_uri: string }>;
};

const IMAGE_FILE = /\.(png|jpe?g|gif|webp|svg|avif|bmp|ico)(\?|#|$)/i;

/** Local names and URI tails, highest priority first. */
const PREDICATE_RANK: Array<[RegExp, number]> = [
  [/(?:^|[/#])logo_url$/i, 0],
  [/(?:^|[/#])depiction$/i, 1],
  [/(?:^|[/#])image$/i, 2],
  [/(?:^|[/#])hasDepiction$/i, 3],
  [/(?:^|[/#])hasDepictionPath$/i, 4],
  [/(?:^|[/#])(photo|thumbnail|img)$/i, 5],
];

function compactKey(value: string): string {
  return value.replace(/[\s-]+/g, '_');
}

function predicateRank(uri: string, label = ''): number | null {
  const keys = [uri, compactKey(uri), compactKey(label)];
  for (const [pattern, rank] of PREDICATE_RANK) {
    if (keys.some(key => key && pattern.test(key))) return rank;
  }
  return null;
}

function valueKind(value: string): number {
  if (/^https?:\/\//i.test(value)) return 0;
  if (value.startsWith('/')) return 1;
  if (value.startsWith('file://')) return 3;
  return 2;
}

function usableImageValue(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || trimmed.toLowerCase() === 'unknown') return false;
  if (/^https?:\/\//i.test(trimmed) || trimmed.startsWith('file://') || trimmed.startsWith('/')) {
    return true;
  }
  return IMAGE_FILE.test(trimmed);
}

/**
 * Pick a depiction from instance properties. Prefers http(s) and site paths over
 * file URIs so the browser can load the image.
 */
export function instanceImageValue(source: InstanceImageSource): string | undefined {
  const candidates: Array<{ value: string; pred: number; kind: number }> = [];
  const add = (predicate: string, label: string, value: string | undefined | null) => {
    if (typeof value !== 'string') return;
    const trimmed = value.trim();
    const pred = predicateRank(predicate, label);
    if (pred == null || !usableImageValue(trimmed)) return;
    candidates.push({ value: trimmed, pred, kind: valueKind(trimmed) });
  };

  for (const [key, value] of Object.entries(source.properties || {})) {
    add(key, key, value);
  }
  for (const row of source.dataProperties || []) {
    add(row.predicate_uri, row.predicate_label || '', row.value);
  }
  for (const row of source.relations || []) {
    add(row.predicate_uri, row.predicate_label || '', row.other_uri);
  }

  candidates.sort((a, b) => a.kind - b.kind || a.pred - b.pred);
  return candidates[0]?.value;
}

const SAME_ORIGIN_PREFIXES = ['/api/', '/app-html/'];

/**
 * Turn a stored image value into an <img src> the web app can fetch.
 * file:// and repo-relative paths go through the same-origin image proxy.
 */
export function browserInstanceImageSrc(value: string | undefined | null): string | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (!trimmed || trimmed.toLowerCase() === 'unknown') return undefined;

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return getLogoUrl(trimmed);
  }
  if (SAME_ORIGIN_PREFIXES.some(prefix => trimmed.startsWith(prefix))) {
    return trimmed;
  }
  if (trimmed.startsWith('file://') || !trimmed.startsWith('/')) {
    return `/api/image-data?raw=1&url=${encodeURIComponent(trimmed)}`;
  }
  return getLogoUrl(trimmed);
}
