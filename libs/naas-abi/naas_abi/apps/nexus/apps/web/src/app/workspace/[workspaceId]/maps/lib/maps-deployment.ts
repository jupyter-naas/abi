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

/** Deployment shows only organization-facility layers in the Maps sidebar. */
export function isMapsOrganizationFacilityOnlyDeployment(): boolean {
  return (
    MAPS_VISIBLE_CATEGORIES != null
    && MAPS_VISIBLE_CATEGORIES.length === 1
    && MAPS_VISIBLE_CATEGORIES[0] === 'organizations-facility'
  );
}

/** Comma-separated feed ids from NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS. */
export function parseMapsDefaultOnFeedIds(
  raw: string | null | undefined,
): ReadonlySet<string> | null {
  const text = (raw ?? '').trim();
  if (!text) return null;
  const ids = text
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  return ids.length ? new Set(ids) : null;
}

export const MAPS_DEFAULT_ON_FEED_IDS = parseMapsDefaultOnFeedIds(
  process.env.NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS,
);

/**
 * Static default feeds from env (before URL / workspace API overrides).
 * Organization-facility-only deployments usually rely on workspace-defaults instead.
 */
export function mapsDefaultOnFeedIds(): ReadonlySet<string> {
  return MAPS_DEFAULT_ON_FEED_IDS ?? new Set();
}

/**
 * Hide File → New layer / New basemap / GeoJSON layers and Settings → New layer.
 * Sidebar filtering uses {@link MAPS_VISIBLE_CATEGORIES} alone — that must not
 * disable these tools when only visible categories are restricted.
 */
export function mapsDeploymentRestrictsLayerCatalog(): boolean {
  return process.env.NEXT_PUBLIC_MAPS_RESTRICT_LAYER_CATALOG === 'true';
}
