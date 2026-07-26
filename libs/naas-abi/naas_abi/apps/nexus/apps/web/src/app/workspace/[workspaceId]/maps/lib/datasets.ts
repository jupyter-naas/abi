export type MapsDatasetId = 'presence' | 'wog';

export interface MapsDataset {
  id: MapsDatasetId;
  title: string;
  description: string;
  /** Sort order in the library (lower first). Presence is always first. */
  order: number;
}

/** Registry of Maps datasets. Presence is the primer; WOG is second. */
export const MAPS_DATASETS: MapsDataset[] = [
  {
    id: 'presence',
    title: 'Here',
    description: 'Your devices and the Zen GCP server on one map.',
    order: 0,
  },
  {
    id: 'wog',
    title: 'World Organization Graph',
    description: 'Search organizations from the WOG index.',
    order: 1,
  },
];

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
