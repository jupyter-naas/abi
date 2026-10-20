import type { MapsPinMarker } from './leaflet-map';
import { resolveMapsPinImageUrl } from './maps-pin-image-url';
import { featureToPinPartial, isMapsFeatureCollection } from './maps-pin-geojson';
import type { MapsFeedMeta } from './maps-view';

export type { MapsFeedMeta, MapsFeedView } from './maps-view';
export { formatMapsFeedAge, withMapsView } from './maps-view';

export function graphObjectHref(workspaceId: string, graphUri: string, entityUri: string): string {
  const query = new URLSearchParams({graph: graphUri, selected: entityUri});
  return `/workspace/${encodeURIComponent(workspaceId)}/graph/individuals?${query}`;
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function httpsUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  try {
    return new URL(value).protocol === 'https:' ? value : undefined;
  } catch {
    return undefined;
  }
}

function evidenceSources(value: MapsPinMarker['sources']): MapsPinMarker['sources'] {
  return Array.isArray(value) ? value.filter((s) => {
    try { return typeof s.title === 'string' && ['http:', 'https:'].includes(new URL(s.url).protocol); }
    catch { return false; }
  }).map(({title, url}) => ({title, url})) : [];
}

export interface MapsFeedPayload {
  pins?: Array<Partial<MapsPinMarker> & {
    id?: string;
    lat?: number;
    lng?: number;
    label?: string;
    detail?: string;
    color?: string;
    size?: number;
  }>;
  coverage?: { pins?: Array<Partial<MapsPinMarker>> } | string;
  coverageLabel?: string;
  count?: number;
  empty?: boolean;
  reason?: string;
  message?: string;
  error?: string;
  source?: string;
  attribution?: string;
  observedAt?: string;
  stale?: boolean;
  status?: string;
  needsKey?: boolean;
}

export interface MapsFeedResult extends MapsFeedMeta {
  pins: MapsPinMarker[];
  coveragePins?: MapsPinMarker[];
  reason?: string;
  empty?: boolean;
}

function asPinRecords(value: unknown): Array<Partial<MapsPinMarker>> | undefined {
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (item && typeof item === 'object' && (item as {type?: string}).type === 'Feature') {
        return featureToPinPartial(item);
      }
      return item as Partial<MapsPinMarker>;
    });
  }
  if (!value || typeof value !== 'object') return undefined;
  const obj = value as Record<string, unknown>;
  if (Array.isArray(obj.features)) return asPinRecords(obj.features);
  const values = Object.values(obj);
  if (!values.length || values.some((item) => !item || typeof item !== 'object' || Array.isArray(item))) {
    return undefined;
  }
  const records = values.map((item) => {
    const rec = item as Record<string, unknown>;
    return rec.type === 'Feature' || rec.geometry ? featureToPinPartial(item) : item as Partial<MapsPinMarker>;
  });
  return records.some((record) => record.lat != null && record.lng != null) ? records : undefined;
}

/**
 * Accept a pin array, Maps feed object, GeoJSON FeatureCollection, or pin dict.
 * Spreading the wrapper itself throws `loaded is not iterable`.
 */
export function normalizeFeedLoad(loaded: unknown): MapsFeedResult {
  if (Array.isArray(loaded)) {
    const pins = parseFeedPins(loaded);
    return {pins, empty: pins.length === 0};
  }
  if (!loaded || typeof loaded !== 'object') {
    throw new TypeError('Map feed did not return locations');
  }
  const feed = loaded as MapsFeedPayload & {features?: unknown; type?: string; coveragePins?: unknown};
  const geoJson = isMapsFeatureCollection(loaded) ? (loaded as { features: unknown }) : null;
  const pinRecords = geoJson
    ? asPinRecords(geoJson.features)
    : asPinRecords(feed.pins) ?? asPinRecords(feed.features) ?? asPinRecords(feed);
  const coverageObject =
    feed.coverage && typeof feed.coverage === 'object' && !Array.isArray(feed.coverage)
      ? feed.coverage as {pins?: unknown; features?: unknown; type?: string}
      : undefined;
  const coverageRecords =
    asPinRecords(coverageObject?.features)
    ?? asPinRecords(coverageObject?.pins)
    ?? asPinRecords(feed.coveragePins);
  const looksLikeFeed = geoJson != null || 'pins' in feed || 'features' in feed || 'coverage' in feed
    || 'coveragePins' in feed || 'empty' in feed || 'needsKey' in feed;
  if (pinRecords === undefined && coverageRecords === undefined && !looksLikeFeed) {
    throw new TypeError('Map feed did not return locations');
  }
  const pins = parseFeedPins(pinRecords);
  const allowedIds = new Set(pins.map((pin) => pin.id));
  const coveragePins = coverageRecords ? parseFeedPins(coverageRecords).map((pin) => ({
    ...pin, memberIds: pin.memberIds?.filter((id) => allowedIds.has(id)) ?? [],
  })) : undefined;
  const coverageLabel =
    typeof feed.coverageLabel === 'string'
      ? feed.coverageLabel
      : typeof feed.coverage === 'string'
        ? feed.coverage
        : undefined;
  return {
    pins,
    coveragePins,
    reason: feed.reason || feed.message,
    empty: Boolean(feed.empty || feed.needsKey || pins.length === 0),
    source: typeof feed.source === 'string' ? feed.source : undefined,
    attribution: typeof feed.attribution === 'string' ? feed.attribution : undefined,
    observedAt: typeof feed.observedAt === 'string' ? feed.observedAt : undefined,
    stale: feed.stale === true,
    needsKey: feed.needsKey === true,
    status: typeof feed.status === 'string' ? feed.status : undefined,
    coverage: coverageLabel,
  };
}

/** Fetch a Maps /api/maps/* JSON pin payload (empty/needsKey stays empty, not thrown). */
export async function fetchMapsFeedPins(
  url: string,
  signal?: AbortSignal,
  headers?: HeadersInit,
  cache: RequestCache = 'no-store',
): Promise<MapsFeedResult> {
  const res = await fetch(url, { signal, headers, cache });
  const data = (await res.json()) as MapsFeedPayload & {type?: string; features?: unknown[]};
  const hasLocations =
    (Array.isArray(data.pins) && data.pins.length > 0)
    || (data.type === 'FeatureCollection' && Array.isArray(data.features) && data.features.length > 0);
  if (!res.ok && !hasLocations && !data.empty && !data.needsKey) {
    throw new Error(data.error || data.message || `Feed ${res.status}`);
  }
  return normalizeFeedLoad(data);
}

function hexColor(value: unknown): string | undefined {
  return typeof value === 'string' && /^#[0-9a-f]{3,8}$/i.test(value) ? value : undefined;
}

function parseFeedPins(input: Array<Partial<MapsPinMarker>> | undefined): MapsPinMarker[] {
  const pins: MapsPinMarker[] = [];
  for (const p of Array.isArray(input) ? input : []) {
    if (!p || typeof p !== 'object') continue;
    if (p.lat == null || p.lng == null) continue;
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lng) || Math.abs(p.lat) > 90 || Math.abs(p.lng) > 180) continue;
    pins.push({
      id: String(p.id ?? `${p.lat},${p.lng}`),
      lat: p.lat,
      lng: p.lng,
      label: text(p.label) ?? 'Point',
      detail: text(p.detail),
      color: /^#[0-9a-f]{3,8}$/i.test(p.color ?? '') ? p.color : undefined,
      size: typeof p.size === 'number' ? Math.min(30, Math.max(4, p.size)) : undefined,
      entityUri: text(p.entityUri), graphUri: text(p.graphUri), classLabel: text(p.classLabel),
      classLabels: Array.isArray(p.classLabels) ? p.classLabels.filter((v): v is string => typeof v === 'string' && v.trim().length > 0) : undefined,
      // Set on the combined map (layer / feed of the pin): grouping and badges need them.
      layerId: text(p.layerId), layerColor: hexColor(p.layerColor),
      feedId: text(p.feedId), feedColor: hexColor(p.feedColor), feedTitle: text(p.feedTitle),
      featureId: text(p.featureId),
      country: text(p.country), precision: text(p.precision), observedAt: text(p.observedAt),
      sources: evidenceSources(p.sources),
      memberIds: Array.isArray(p.memberIds) ? p.memberIds.filter((id): id is string => typeof id === "string") : undefined,
      relationships: Array.isArray(p.relationships) ? p.relationships.filter((r) => r && typeof r.label === 'string' && typeof r.value === 'string').map((r) => ({label:r.label,value:r.value,entityUri:text(r.entityUri)})) : [],
      markerIcon: text((p as { markerIcon?: unknown }).markerIcon),
      markerLogoUrl: resolveMapsPinImageUrl((p as { markerLogoUrl?: unknown }).markerLogoUrl),
      address: text(p.address),
      photoUrl: httpsUrl(p.photoUrl),
      photoSource: httpsUrl(p.photoSource),
      streetViewUrl: httpsUrl(p.streetViewUrl),
      streetViewFallbackUrl: httpsUrl(p.streetViewFallbackUrl),
      imageSearchUrl: httpsUrl(p.imageSearchUrl),
      websiteUrl: httpsUrl(p.websiteUrl),
      phone: text(p.phone),
    });
  }
  return pins;
}

/** Parse EONET events JSON into map pins (latest Point geometry per event). */
export function eonetEventsToPins(
  data: {
    events?: Array<{
      id?: string;
      title?: string;
      link?: string;
      categories?: Array<{ id?: string; title?: string }>;
      geometry?: Array<{
        type?: string;
        coordinates?: number[];
        date?: string;
      }>;
    }>;
  },
  color = '#7c3aed',
): MapsPinMarker[] {
  const pins: MapsPinMarker[] = [];
  for (const event of data.events ?? []) {
    const geoms = event.geometry ?? [];
    const point = [...geoms].reverse().find((g) => g.type === 'Point');
    const coords = point?.coordinates;
    if (!coords || coords.length < 2) continue;
    const [lng, lat] = coords;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    const cat = event.categories?.[0]?.title ?? 'EONET';
    const catId = event.categories?.[0]?.id;
    pins.push({
      id: String(event.id ?? `${lat},${lng}`),
      lat,
      lng,
      label: event.title ?? 'EONET event',
      detail: `${cat}${point?.date ? ` · ${point.date}` : ''}`,
      color:
        catId === 'wildfires'
          ? '#dc2626'
          : catId === 'volcanoes'
            ? '#7c3aed'
            : catId === 'severeStorms'
              ? '#2563eb'
              : catId === 'earthquakes'
                ? '#ea580c'
                : color,
      size: 9,
    });
  }
  return pins;
}
