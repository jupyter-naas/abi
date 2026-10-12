import type { MapsDatasetCategory } from './datasets';

const ALL_CATEGORIES: MapsDatasetCategory[] = [
  'environment',
  'sigint',
  'situation',
  'organizations-facility',
  'custom',
];

/** Comma-separated sidebar groups from NEXT_PUBLIC_MAPS_VISIBLE_CATEGORIES. */
export function parseMapsVisibleCategories(
  raw: string | null | undefined,
): MapsDatasetCategory[] | null {
  const text = (raw ?? '').trim();
  if (!text) return null;
  const allowed = new Set<string>(ALL_CATEGORIES);
  const picked = text
    .split(',')
    .map((part) => part.trim())
    .filter((id): id is MapsDatasetCategory => allowed.has(id));
  return picked.length ? picked : null;
}

export const MAPS_VISIBLE_CATEGORIES = parseMapsVisibleCategories(
  process.env.NEXT_PUBLIC_MAPS_VISIBLE_CATEGORIES,
);

export function isMapsCategoryVisible(category: MapsDatasetCategory): boolean {
  if (!MAPS_VISIBLE_CATEGORIES) return true;
  return MAPS_VISIBLE_CATEGORIES.includes(category);
}

export function isMapsLayerGroupIdVisible(groupId: string): boolean {
  if (groupId.startsWith('user-')) return isMapsCategoryVisible('custom');
  return isMapsCategoryVisible(groupId as MapsDatasetCategory);
}

/** BOB-style deployment: only organization facility custom layers in Maps. */
export function isMapsOrganizationFacilityOnlyDeployment(): boolean {
  return (
    MAPS_VISIBLE_CATEGORIES != null
    && MAPS_VISIBLE_CATEGORIES.length === 1
    && MAPS_VISIBLE_CATEGORIES[0] === 'organizations-facility'
  );
}

/** Default GeoJSON feed when {@link isMapsOrganizationFacilityOnlyDeployment} is true. */
export const FORVIS_MAZARS_FACILITIES_FEED_ID = 'forvis-mazars-facilities';

/**
 * Hide File → New layer / New basemap / GeoJSON layers and Settings → New layer.
 * Sidebar filtering uses {@link MAPS_VISIBLE_CATEGORIES} alone — that must not
 * disable these tools (BOB sets visible categories without locking the catalog).
 */
export function mapsDeploymentRestrictsLayerCatalog(): boolean {
  return process.env.NEXT_PUBLIC_MAPS_RESTRICT_LAYER_CATALOG === 'true';
}
