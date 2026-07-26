export type MapsDatasetId =
  | 'openstreetmap'
  | 'earthquakes'
  | 'wildfires'
  | 'temperature'
  | 'natural-earth'
  | 'gdacs'
  | 'eonet-all'
  | 'openaq'
  | 'nws-alerts'
  | 'tropical-storms'
  | 'volcanoes'
  | 'flights'
  | 'conflict'
  | 'news'
  | 'ais'
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
 * - Public: first-class situation-awareness layers owned by Nexus Maps
 * - Private: presence ("Here") : workspace user's devices / infra
 * - Custom: WOG : NaasAI domain graph
 *
 * World Situation Room (marketplace alpha) is a legacy demo for these feeds.
 * Do not import from naas_abi_marketplace/.../wsr. Prefer Maps API routes under
 * /api/maps/ for CORS / User-Agent proxies.
 */
export const MAPS_DATASETS: MapsDataset[] = [
  {
    id: 'openstreetmap',
    title: 'OpenStreetMap',
    description: 'Public OSM / CARTO basemap tiles for Maps canvases.',
    category: 'public',
    icon: 'Globe',
    order: 0,
  },
  {
    id: 'earthquakes',
    title: 'Earthquakes',
    description: 'USGS GeoJSON feed (M≥2.5, past day). Free public layer.',
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
    description: 'Natural Earth 110m country borders (GeoJSON).',
    category: 'public',
    icon: 'Layers',
    order: 4,
  },
  {
    id: 'gdacs',
    title: 'GDACS',
    description:
      'UN GDACS multi-hazard events (quakes, storms, floods, volcanoes, drought, wildfire).',
    category: 'public',
    icon: 'AlertTriangle',
    order: 5,
  },
  {
    id: 'eonet-all',
    title: 'EONET Events',
    description:
      'NASA EONET open natural events (all categories, last 30 days). Wildfires stay as a dedicated layer.',
    category: 'public',
    icon: 'Sparkles',
    order: 6,
  },
  {
    id: 'openaq',
    title: 'Air Quality',
    description:
      'OpenAQ monitoring locations. Requires OPENAQ_API_KEY on the Maps host.',
    category: 'public',
    icon: 'Wind',
    order: 7,
  },
  {
    id: 'nws-alerts',
    title: 'NWS Alerts',
    description:
      'US NWS active weather alerts (centroid pins). Proxied with a Maps User-Agent.',
    category: 'public',
    icon: 'Bell',
    order: 8,
  },
  {
    id: 'tropical-storms',
    title: 'Tropical Storms',
    description: 'NHC active tropical cyclones (CurrentStorms GeoJSON-compatible).',
    category: 'public',
    icon: 'CloudLightning',
    order: 9,
  },
  {
    id: 'volcanoes',
    title: 'Volcanoes',
    description: 'NASA EONET open volcano events (last 90 days).',
    category: 'public',
    icon: 'Mountain',
    order: 10,
  },
  {
    id: 'flights',
    title: 'Flights',
    description:
      'Live aircraft sample via airplanes.live (Maps-owned /api/maps/flights proxy).',
    category: 'public',
    icon: 'Plane',
    order: 11,
  },
  {
    id: 'conflict',
    title: 'Conflict Sites',
    description:
      'Curated static OSINT conflict pins (Maps-owned list under maps/lib).',
    category: 'public',
    icon: 'Crosshair',
    order: 12,
  },
  {
    id: 'news',
    title: 'News',
    description:
      'World RSS headlines (BBC / Al Jazeera / Reuters) mapped to light region geocodes.',
    category: 'public',
    icon: 'Newspaper',
    order: 13,
  },
  {
    id: 'ais',
    title: 'AIS Vessels',
    description:
      'Reserved AIS layer. No free keyless feed configured; honest empty state until licensed.',
    category: 'public',
    icon: 'Ship',
    order: 14,
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

/**
 * Public feed URLs and Maps-owned API proxies.
 * Prefer /api/maps/* when the upstream needs CORS, User-Agent, or a secret.
 */
export const MAPS_PUBLIC_FEEDS = {
  earthquakes:
    'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson',
  wildfires:
    'https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open&days=7',
  eonetAll:
    'https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=30',
  volcanoes:
    'https://eonet.gsfc.nasa.gov/api/v3/events?category=volcanoes&status=open&days=90',
  firmsWms: 'https://firms.modaps.eosdis.nasa.gov/mapserver/wms/fires/',
  temperature: 'https://api.open-meteo.com/v1/forecast',
  naturalEarth:
    'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson',
  gdacs: '/api/maps/gdacs',
  openaq: '/api/maps/openaq',
  nwsAlerts: '/api/maps/nws-alerts',
  tropicalStorms: '/api/maps/tropical-storms',
  flights: '/api/maps/flights',
  news: '/api/maps/news',
  ais: '/api/maps/ais',
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
