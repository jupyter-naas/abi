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

export function mapsDeploymentRestrictsLayerCatalog(): boolean {
  return MAPS_VISIBLE_CATEGORIES != null;
}
