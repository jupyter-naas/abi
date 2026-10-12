import type { MapsPinMarker } from './leaflet-map';

/** Nexus metadata on a GeoJSON FeatureCollection (foreign members). */
export type MapsLayerGeoJsonMeta = {
  layerId: string;
  layerTitle?: string;
  fetchedAt: string;
  featureCount: number;
};

export type MapsGeoJsonFeature = {
  type: 'Feature';
  id?: string;
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: Record<string, unknown> | null;
};

export type MapsLayerFeatureCollection = {
  type: 'FeatureCollection';
  features: MapsGeoJsonFeature[];
  nexus?: MapsLayerGeoJsonMeta;
};

const PIN_KEYS = [
  'detail',
  'color',
  'markerIcon',
  'markerLogoUrl',
  'size',
  'entityUri',
  'graphUri',
  'classLabel',
  'classLabels',
  'country',
  'precision',
  'observedAt',
  'sources',
  'memberIds',
  'relationships',
  'address',
  'photoUrl',
  'photoSource',
  'streetViewUrl',
  'streetViewFallbackUrl',
  'imageSearchUrl',
  'websiteUrl',
  'phone',
] as const;

function pinProperties(pin: MapsPinMarker): Record<string, unknown> {
  const properties: Record<string, unknown> = {
    id: pin.id,
    label: pin.label,
  };
  for (const key of PIN_KEYS) {
    const value = pin[key];
    if (value !== undefined && value !== null && value !== '') {
      properties[key] = value;
    }
  }
  return properties;
}

export function pinToFeature(pin: MapsPinMarker): MapsGeoJsonFeature {
  return {
    type: 'Feature',
    id: pin.id,
    geometry: {
      type: 'Point',
      coordinates: [pin.lng, pin.lat],
    },
    properties: pinProperties(pin),
  };
}

export function pinsToFeatureCollection(
  pins: MapsPinMarker[],
  meta: MapsLayerGeoJsonMeta,
): MapsLayerFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: pins.map(pinToFeature),
    nexus: {
      ...meta,
      featureCount: pins.length,
    },
  };
}

/** Loose pin record (Maps API / SPARQL layout) → GeoJSON Point feature. */
export function pinRecordToFeature(
  pin: Record<string, unknown>,
): MapsGeoJsonFeature | null {
  const lat = typeof pin.lat === 'number' ? pin.lat : undefined;
  const lng = typeof pin.lng === 'number' ? pin.lng : undefined;
  if (
    lat == null
    || lng == null
    || !Number.isFinite(lat)
    || !Number.isFinite(lng)
    || Math.abs(lat) > 90
    || Math.abs(lng) > 180
  ) {
    return null;
  }
  const properties: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(pin)) {
    if (key === 'lat' || key === 'lng') continue;
    if (value !== undefined && value !== null && value !== '') {
      properties[key] = value;
    }
  }
  if (typeof properties.label !== 'string' && typeof properties.name === 'string') {
    properties.label = properties.name;
  }
  const id = pin.id != null ? String(pin.id) : undefined;
  return {
    type: 'Feature',
    id,
    geometry: { type: 'Point', coordinates: [lng, lat] },
    properties,
  };
}

export function pinRecordsToFeatures(
  pins: Array<Record<string, unknown>>,
): MapsGeoJsonFeature[] {
  return pins
    .map((pin) => pinRecordToFeature(pin))
    .filter((feature): feature is MapsGeoJsonFeature => feature != null);
}

/** Canonical Maps feed wire body: GeoJSON FeatureCollection + feed metadata. */
export function buildMapsFeedPayload(
  pinRecords: Array<Record<string, unknown>>,
  meta: Record<string, unknown> = {},
): MapsLayerFeatureCollection & Record<string, unknown> {
  const features = pinRecordsToFeatures(pinRecords);
  return {
    type: 'FeatureCollection',
    features,
    count: features.length,
    ...meta,
  };
}

export function isMapsFeatureCollection(
  value: unknown,
): value is MapsLayerFeatureCollection {
  return Boolean(
    value
    && typeof value === 'object'
    && (value as { type?: string }).type === 'FeatureCollection'
    && Array.isArray((value as { features?: unknown }).features),
  );
}

/** GeoJSON Feature or loose feature object → partial pin for normalizeFeedLoad. */
export function featureToPinPartial(feature: unknown): Partial<MapsPinMarker> {
  if (!feature || typeof feature !== 'object') return {};
  const value = feature as Record<string, unknown>;
  const props =
    value.properties && typeof value.properties === 'object'
      ? (value.properties as Record<string, unknown>)
      : {};
  const geometry =
    value.geometry && typeof value.geometry === 'object'
      ? (value.geometry as { type?: string; coordinates?: unknown })
      : undefined;
  const coords =
    geometry?.type === 'Point' && Array.isArray(geometry.coordinates)
      ? geometry.coordinates
      : undefined;
  const lat =
    typeof value.lat === 'number'
      ? value.lat
      : typeof props.lat === 'number'
        ? props.lat
        : typeof coords?.[1] === 'number'
          ? coords[1]
          : undefined;
  const lng =
    typeof value.lng === 'number'
      ? value.lng
      : typeof props.lng === 'number'
        ? props.lng
        : typeof coords?.[0] === 'number'
          ? coords[0]
          : undefined;
  return {
    ...(props as Partial<MapsPinMarker>),
    ...(value as Partial<MapsPinMarker>),
    lat,
    lng,
    id: typeof value.id === 'string' ? value.id : typeof props.id === 'string' ? props.id : undefined,
    label:
      typeof value.label === 'string'
        ? value.label
        : typeof props.label === 'string'
          ? props.label
          : typeof props.name === 'string'
            ? props.name
            : undefined,
  };
}
