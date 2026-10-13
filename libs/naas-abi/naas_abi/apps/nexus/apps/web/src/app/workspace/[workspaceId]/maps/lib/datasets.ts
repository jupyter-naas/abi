export type MapsBuiltinDatasetId =
  | 'earthquakes'
  | 'wildfires'
  | 'temperature'
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
  | 'iss';

/**
 * A built-in id, or the id of a workspace layer record (Settings → Maps).
 * `string & {}` keeps autocomplete for the built-ins.
 */
export type MapsDatasetId = MapsBuiltinDatasetId | (string & {});

export interface MapsDataset {
  id: MapsDatasetId;
  title: string;
  description: string;
  /** Sidebar group label (see maps-layer-groups.ts). */
  group: string;
  /** Lucide icon key (see mapsIconMap). */
  icon: string;
  /** Sort order within a group (lower first). */
  order: number;
  /** Optional brand logo for sidebar and legend (HTTPS or /api/…). */
  layerLogoUrl?: string;
}

/**
 * Built-in Maps data layers. The basemap is separate (see maps-basemaps.ts).
 *
 * Product-specific layers are not hard-coded here: deployments seed layer
 * records server-side (services/maps/seeds.py) and admins manage them in
 * Settings → Maps.
 *
 * World Situation Room (marketplace alpha) is a legacy demo for these feeds.
 * Do not import from naas_abi_marketplace/.../wsr. Prefer Maps API routes under
 * /api/maps/ for CORS / User-Agent proxies.
 */
const MAPS_BUILTIN_DATASETS: MapsDataset[] = [
  {
    id: 'earthquakes',
    title: 'Earthquakes',
    description: 'USGS GeoJSON feed (M≥2.5, past day). Free public layer.',
    group: 'Environment',
    icon: 'Activity',
    order: 2,
  },
  {
    id: 'wildfires',
    title: 'Wildfires',
    description:
      'EONET named open wildfires (7d). Optional FIRMS VIIRS 24h WMS when FIRMS_MAP_KEY is set.',
    group: 'Environment',
    icon: 'Flame',
    order: 3,
  },
  {
    id: 'temperature',
    title: 'Temperature',
    description:
      'Current 2m air temperature city samples via Open-Meteo (free, no API key).',
    group: 'Environment',
    icon: 'Thermometer',
    order: 8,
  },
  {
    id: 'gdacs',
    title: 'GDACS',
    description:
      'UN GDACS multi-hazard events (quakes, storms, floods, volcanoes, drought, wildfire).',
    group: 'Environment',
    icon: 'AlertTriangle',
    order: 1,
  },
  {
    id: 'eonet-all',
    title: 'EONET Events',
    description:
      'NASA EONET open natural events (all categories, last 30 days). Wildfires stay as a dedicated layer.',
    group: 'Environment',
    icon: 'Sparkles',
    order: 7,
  },
  {
    id: 'openaq',
    title: 'Air Quality',
    description:
      'OpenAQ when OPENAQ_API_KEY is set; Open-Meteo PM2.5 city samples otherwise.',
    group: 'Environment',
    icon: 'Wind',
    order: 9,
  },
  {
    id: 'nws-alerts',
    title: 'NWS Alerts',
    description:
      'US NWS active weather alerts (centroid pins). Proxied with a Maps User-Agent.',
    group: 'Environment',
    icon: 'Bell',
    order: 6,
  },
  {
    id: 'tropical-storms',
    title: 'Tropical Storms',
    description: 'NHC active tropical cyclones (CurrentStorms GeoJSON-compatible).',
    group: 'Environment',
    icon: 'CloudLightning',
    order: 5,
  },
  {
    id: 'volcanoes',
    title: 'Volcanoes',
    description: 'NASA EONET open volcano events (last 90 days).',
    group: 'Environment',
    icon: 'Mountain',
    order: 4,
  },
  {
    id: 'flights',
    title: 'Flights',
    description:
      'Live aircraft: viewport query via adsb.lol, global sample via airplanes.live.',
    group: 'SIGINT',
    icon: 'Plane',
    order: 1,
  },
  {
    id: 'conflict',
    title: 'Conflict Sites',
    description:
      'Curated static OSINT conflict pins (Maps-owned list under maps/lib).',
    group: 'Situation',
    icon: 'Crosshair',
    order: 1,
  },
  {
    id: 'gulf-strikes',
    title: 'Gulf Strikes',
    description:
      'Live Gulf / Iran / Israel strike headlines from RSS, geocoded to theater sites via /api/maps/gulf-strikes.',
    group: 'Situation',
    icon: 'Rocket',
    order: 2,
  },
  {
    id: 'news',
    title: 'News',
    description:
      'World RSS headlines (BBC / Al Jazeera / Reuters) mapped to light region geocodes.',
    group: 'Situation',
    icon: 'Newspaper',
    order: 3,
  },
  {
    id: 'ais',
    title: 'AIS Vessels',
    description:
      'Live ships via AISStream when AISSTREAM_API_KEY is set on nexus-web. Honest empty state without a key.',
    group: 'SIGINT',
    icon: 'Ship',
    order: 2,
  },
  {
    id: 'iss',
    title: 'ISS',
    description:
      'International Space Station current position (open-notify). Thin CelesTrak substitute.',
    group: 'SIGINT',
    icon: 'Satellite',
    order: 3,
  },
];

/** Built-in feeds drawn by this app; layer records come from `/api/maps/catalog`. */
export const MAPS_DATASETS: MapsDataset[] = MAPS_BUILTIN_DATASETS;

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

/** Authed proxy for a feed layer record (`feed_type: geojson_url`, see app/api/maps/custom). */
export function mapsCustomFeedUrl(datasetId: string, workspaceId: string): string {
  const query = new URLSearchParams({ workspace_id: workspaceId });
  return `/api/maps/custom/${encodeURIComponent(datasetId)}?${query.toString()}`;
}

export function getMapsDatasetsByGroup(group: string): MapsDataset[] {
  const key = group.trim().toLowerCase();
  return MAPS_DATASETS.filter((d) => d.group.toLowerCase() === key).sort(
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
