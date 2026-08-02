import {
  MAPS_CUSTOM_DATASETS,
  type MapsCustomDataset,
} from '@/lib/maps-custom-datasets';

export type MapsBuiltinDatasetId =
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
  | 'gulf-strikes'
  | 'news'
  | 'ais'
  | 'iss'
  | 'presence';

/**
 * A built-in id, or an id a deployment registered through
 * NEXT_PUBLIC_MAPS_CUSTOM_DATASETS. `string & {}` keeps autocomplete for the
 * built-ins while still admitting configured Custom ids.
 */
export type MapsDatasetId = MapsBuiltinDatasetId | (string & {});

/** Same source buckets as Search (Public / Private / Custom). Custom stays empty upstream. */
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
 * Built-in Maps datasets, grouped like Search sources:
 * - Public: first-class situation-awareness layers owned by Nexus Maps
 * - Private: presence ("Here"): workspace user's devices / infra
 *
 * Custom is the extension point and stays empty here: product-specific datasets
 * belong to the deployment, registered through NEXT_PUBLIC_MAPS_CUSTOM_DATASETS
 * (see MAPS_CUSTOM_DATASETS), not hard-coded into upstream ABI.
 *
 * World Situation Room (marketplace alpha) is a legacy demo for these feeds.
 * Do not import from naas_abi_marketplace/.../wsr. Prefer Maps API routes under
 * /api/maps/ for CORS / User-Agent proxies.
 */
const MAPS_BUILTIN_DATASETS: MapsDataset[] = [
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
      'EONET named open wildfires (7d). Optional FIRMS VIIRS 24h WMS when FIRMS_MAP_KEY is set.',
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
      'OpenAQ when OPENAQ_API_KEY is set; Open-Meteo PM2.5 city samples otherwise.',
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
    id: 'gulf-strikes',
    title: 'Gulf Strikes',
    description:
      'Live Gulf / Iran / Israel strike headlines from RSS, geocoded to theater sites via /api/maps/gulf-strikes.',
    category: 'public',
    icon: 'Rocket',
    order: 13,
  },
  {
    id: 'news',
    title: 'News',
    description:
      'World RSS headlines (BBC / Al Jazeera / Reuters) mapped to light region geocodes.',
    category: 'public',
    icon: 'Newspaper',
    order: 14,
  },
  {
    id: 'ais',
    title: 'AIS Vessels',
    description:
      'Reserved AIS layer. No free keyless feed configured; honest empty state until licensed.',
    category: 'public',
    icon: 'Ship',
    order: 15,
  },
  {
    id: 'iss',
    title: 'ISS',
    description:
      'International Space Station current position (open-notify). Thin CelesTrak substitute.',
    category: 'public',
    icon: 'Satellite',
    order: 16,
  },
  {
    id: 'presence',
    title: 'Here',
    description: 'Your devices and the Zen GCP server on one map.',
    category: 'private',
    icon: 'Laptop',
    order: 0,
  },
];

const MAPS_BUILTIN_DATASET_IDS = new Set(MAPS_BUILTIN_DATASETS.map((d) => d.id));

function toMapsDataset(custom: MapsCustomDataset): MapsDataset {
  return {
    id: custom.id,
    title: custom.title,
    description: custom.description,
    category: 'custom',
    icon: custom.icon,
    order: custom.order,
  };
}

/**
 * Built-in datasets plus whatever this deployment registered under Custom.
 * A configured id that shadows a built-in is ignored so the Public/Private
 * layers can never be replaced by config.
 */
export const MAPS_DATASETS: MapsDataset[] = [
  ...MAPS_BUILTIN_DATASETS,
  ...MAPS_CUSTOM_DATASETS.filter((d) => !MAPS_BUILTIN_DATASET_IDS.has(d.id)).map(
    toMapsDataset,
  ),
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
  /** FIRMS WMS proxy; enabled only when FIRMS_MAP_KEY is set on nexus-web. */
  firms: '/api/maps/firms',
  temperature: 'https://api.open-meteo.com/v1/forecast',
  naturalEarth:
    'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson',
  gdacs: '/api/maps/gdacs',
  openaq: '/api/maps/openaq',
  nwsAlerts: '/api/maps/nws',
  tropicalStorms: '/api/maps/nhc',
  flights: '/api/maps/flights',
  gulfStrikes: '/api/maps/gulf-strikes',
  news: '/api/maps/news',
  ais: '/api/maps/ais',
  iss: '/api/maps/iss',
} as const;

/** Authed proxy for a configured Custom dataset (see maps-custom-datasets). */
export function mapsCustomFeedUrl(datasetId: string, workspaceId: string): string {
  const query = new URLSearchParams({ workspace_id: workspaceId });
  return `/api/maps/custom/${encodeURIComponent(datasetId)}?${query.toString()}`;
}

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
