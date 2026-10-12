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
  'size',
  'entityUri',
  'graphUri',
  'classLabel',
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
