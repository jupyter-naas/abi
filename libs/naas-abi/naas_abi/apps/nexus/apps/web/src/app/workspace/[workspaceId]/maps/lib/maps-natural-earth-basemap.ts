import type { GeoJSON as GeoJSONLayer, Map as LeafletMap } from 'leaflet';

export type NaturalEarthFeatureCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  Record<string, unknown>
>;

let bordersPromise: Promise<NaturalEarthFeatureCollection> | null = null;

/** Natural Earth 110m countries (proxied at /api/maps/natural-earth). */
export function fetchNaturalEarthCountries(): Promise<NaturalEarthFeatureCollection> {
  if (!bordersPromise) {
    bordersPromise = fetch('/api/maps/natural-earth')
      .then(async (response) => {
        if (!response.ok) throw new Error('Country borders unavailable');
        const data = (await response.json()) as NaturalEarthFeatureCollection;
        if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
          throw new Error('Invalid country borders');
        }
        return data;
      })
      .catch((error) => {
        bordersPromise = null;
        throw error;
      });
  }
  return bordersPromise;
}

const NATURAL_EARTH_ATTRIBUTION =
  '&copy; <a href="https://www.naturalearthdata.com/">Natural Earth</a>';

export function addNaturalEarthBasemapLayer(
  L: typeof import('leaflet'),
  map: LeafletMap,
  geojson: NaturalEarthFeatureCollection,
): GeoJSONLayer {
  const layer = L.geoJSON(geojson, {
    style: () => ({
      className: 'maps-basemap-countries-path',
      weight: 1,
      fillOpacity: 1,
    }),
    attribution: NATURAL_EARTH_ATTRIBUTION,
    interactive: false,
  });
  layer.addTo(map);
  layer.bringToBack();
  return layer;
}
