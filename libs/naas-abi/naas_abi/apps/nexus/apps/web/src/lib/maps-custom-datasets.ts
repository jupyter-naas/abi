/**
 * Custom Maps datasets: the extension point product overlays register into.
 *
 * Upstream ABI ships no Custom datasets — Maps stays generic and the bucket is
 * hidden until a deployment fills it. An operator registers their own layers by
 * setting NEXT_PUBLIC_MAPS_CUSTOM_DATASETS to a JSON array of descriptors, so a
 * layer only ever appears where someone has pointed it at a backend that exists.
 *
 * `endpoint` must be a path on the Nexus API: the authed proxy at
 * /api/maps/custom/[datasetId] forwards the caller's Bearer token, so accepting
 * an absolute URL here would hand that token to a third-party host.
 */

export interface MapsCustomDataset {
  /** Route-safe id, unique within the Maps registry. */
  id: string;
  title: string;
  description: string;
  /** Lucide icon key (see mapsIconMap); unknown keys fall back to Map. */
  icon: string;
  /** Sort order within the Custom bucket (lower first). */
  order: number;
  /** Nexus API path returning a Maps pin payload ({ pins: [...] }). */
  endpoint: string;
  emptyTitle?: string;
  emptyBody?: string;
  /** Meta line shown when pins load; "{count}" is replaced with the pin count. */
  metaLabel?: string;
  sourceLabel?: string;
  fitMaxZoom?: number;
}

/** Route-safe: keeps a dataset id from escaping its /api/maps/custom segment. */
const DATASET_ID_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

function readString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function readNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function readOptionalString(value: unknown): string | undefined {
  const text = readString(value);
  return text.length > 0 ? text : undefined;
}

/** Path on the Nexus API — never absolute, never protocol-relative. */
function isNexusApiPath(endpoint: string): boolean {
  return endpoint.startsWith('/') && !endpoint.startsWith('//');
}

function toCustomDataset(entry: unknown, index: number): MapsCustomDataset | null {
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return null;
  const raw = entry as Record<string, unknown>;

  const id = readString(raw.id);
  const title = readString(raw.title);
  const endpoint = readString(raw.endpoint);
  if (!DATASET_ID_PATTERN.test(id)) return null;
  if (!title || !isNexusApiPath(endpoint)) return null;

  return {
    id,
    title,
    description: readString(raw.description),
    icon: readString(raw.icon) || 'Map',
    order: readNumber(raw.order, index),
    endpoint,
    emptyTitle: readOptionalString(raw.emptyTitle),
    emptyBody: readOptionalString(raw.emptyBody),
    metaLabel: readOptionalString(raw.metaLabel),
    sourceLabel: readOptionalString(raw.sourceLabel),
    fitMaxZoom: typeof raw.fitMaxZoom === 'number' ? raw.fitMaxZoom : undefined,
  };
}

/**
 * Parse the configured descriptors. Invalid entries are dropped rather than
 * thrown, so one bad line in a deployment's config cannot take Maps down.
 */
export function parseMapsCustomDatasets(
  raw: string | null | undefined,
): MapsCustomDataset[] {
  const text = (raw ?? '').trim();
  if (!text) return [];

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    console.warn(
      'NEXT_PUBLIC_MAPS_CUSTOM_DATASETS is not valid JSON; no Custom Maps datasets registered.',
    );
    return [];
  }
  if (!Array.isArray(parsed)) {
    console.warn(
      'NEXT_PUBLIC_MAPS_CUSTOM_DATASETS must be a JSON array; no Custom Maps datasets registered.',
    );
    return [];
  }

  const datasets: MapsCustomDataset[] = [];
  const seen = new Set<string>();
  let dropped = 0;
  parsed.forEach((entry, index) => {
    const dataset = toCustomDataset(entry, index);
    if (!dataset || seen.has(dataset.id)) {
      dropped += 1;
      return;
    }
    seen.add(dataset.id);
    datasets.push(dataset);
  });
  if (dropped > 0) {
    console.warn(
      `Ignored ${dropped} invalid NEXT_PUBLIC_MAPS_CUSTOM_DATASETS entr${dropped === 1 ? 'y' : 'ies'} ` +
        '(each needs a route-safe id, a title, and an endpoint path starting with "/").',
    );
  }
  return datasets.sort((a, b) => a.order - b.order);
}

export const MAPS_CUSTOM_DATASETS: MapsCustomDataset[] = parseMapsCustomDatasets(
  process.env.NEXT_PUBLIC_MAPS_CUSTOM_DATASETS,
);

export function getMapsCustomDataset(
  id: string | null | undefined,
): MapsCustomDataset | null {
  if (!id) return null;
  return MAPS_CUSTOM_DATASETS.find((d) => d.id === id) ?? null;
}
