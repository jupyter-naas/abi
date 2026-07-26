export type MapsDatasetId =
  | 'openstreetmap'
  | 'earthquakes'
  | 'wildfires'
  | 'temperature'
  | 'natural-earth'
  | 'presence'
  | 'wog';

/** Same source buckets as Search (Public / Private / Custom). */
export type MapsDatasetCategory = 'public' | 'private' | 'custom';

export interface MapsDataset {
  id: MapsDatasetId;
  title: string;
  description: string;
  category: MapsDatasetCategory;
  /** Lucide icon key (see mapsIconMap). */
  icon: string;
  /** Sort order within a category (lower first). */
  order: number;
}

export const MAPS_CATEGORIES: {
  id: MapsDatasetCategory;
  label: string;
}[] = [
  { id: 'public', label: 'Public' },
  { id: 'private', label: 'Private' },
  { id: 'custom', label: 'Custom' },
];

/**
 * Registry of Maps datasets, grouped like Search sources:
 * - Public: free open layers (OSM, USGS earthquakes, NASA FIRMS/EONET wildfires,
 *   Open-Meteo temperature, Natural Earth). WSR-adjacent where applicable.
 * - Private: presence ("Here") : workspace user's devices / infra
 * - Custom: WOG : NaasAI domain graph
 */
export const MAPS_DATASETS: MapsDataset[] = [
  {
    id: 'openstreetmap',
    title: 'OpenStreetMap',
    description:
      'Public OSM / CARTO basemap tiles (same stack WSR uses for Nominatim geocoding).',
    category: 'public',
    icon: 'Globe',
    order: 0,
  },
  {
    id: 'earthquakes',
    title: 'Earthquakes',
    description:
      'USGS GeoJSON feed (M≥2.5, past day). Free public layer from World Situation Room.',
    category: 'public',
    icon: 'Activity',
    order: 1,
  },
  {
    id: 'wildfires',
    title: 'Wildfires',
    description:
      'NASA FIRMS VIIRS active fires (last 24h WMS) plus EONET named open wildfires (7d). No API key.',
    category: 'public',
    icon: 'Flame',
    order: 2,
  },
  {
    id: 'temperature',
    title: 'Temperature',
    description:
      'Current 2m air temperature city samples via Open-Meteo (free, no API key).',
    category: 'public',
    icon: 'Thermometer',
    order: 3,
  },
  {
    id: 'natural-earth',
    title: 'Natural Earth',
    description:
      'Natural Earth 110m country borders (GeoJSON). Static public layer used by WSR.',
    category: 'public',
    icon: 'Layers',
    order: 4,
  },
  {
    id: 'presence',
    title: 'Here',
    description: 'Your devices and the Zen GCP server on one map.',
    category: 'private',
    icon: 'Laptop',
    order: 0,
  },
  {
    id: 'wog',
    title: 'World Organization Graph',
    description: 'Search WOG orgs and plot geocoded headquarters.',
    category: 'custom',
    icon: 'Building2',
    order: 0,
  },
];

/** Free public feed URLs (browser-fetchable; stubs may load empty on CORS/network fail). */
export const MAPS_PUBLIC_FEEDS = {
  earthquakes:
    'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson',
  wildfires:
    'https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open&days=7',
  firmsWms: 'https://firms.modaps.eosdis.nasa.gov/mapserver/wms/fires/',
  temperature: 'https://api.open-meteo.com/v1/forecast',
  naturalEarth:
    'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson',
} as const;

export function getMapsDatasetsByCategory(
  category: MapsDatasetCategory,
): MapsDataset[] {
  return MAPS_DATASETS.filter((d) => d.category === category).sort(
    (a, b) => a.order - b.order,
  );
}

export function getMapsDataset(id: string | null | undefined): MapsDataset | null {
  if (!id) return null;
  return MAPS_DATASETS.find((d) => d.id === id) ?? null;
}

export function isMapsDatasetId(id: string): id is MapsDatasetId {
  return MAPS_DATASETS.some((d) => d.id === id);
}

/** GCP us-central1 (Council Bluffs, Iowa), abi-naas-app. */
export const GCP_PRESENCE_PIN = {
  id: 'gcp',
  lat: 41.2619,
  lng: -95.8608,
  label: 'GCP · abi-naas-app · us-central1-a',
} as const;

export const MOBILE_GEO_STORAGE_KEY = 'nexus-maps-mobile-geo';
