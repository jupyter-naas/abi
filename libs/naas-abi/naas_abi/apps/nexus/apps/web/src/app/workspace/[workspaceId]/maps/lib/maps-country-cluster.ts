import type { MapsPinMarker } from './leaflet-map';
import {
  CONTINENT_CENTERS,
  continentForGrouping,
  findCountryCenter,
  normalizeCountryName,
  type CountryCenter,
  type CountryCenterIndex,
} from './maps-country-centers';

/** From this zoom pins are shown one by one (grouping stops). */
export const COUNTRY_CLUSTER_EXPAND_ZOOM = 5;
/** Grouping by continent: continents below this zoom, then countries. */
export const CONTINENT_CLUSTER_EXPAND_ZOOM = 3;

/** Map grouping: one badge per layer feed (default) or per layer, or none. */
export type MapsGroupBy = 'feed' | 'layer' | 'off';
/** Map grouping area. */
export type MapsGroupArea = 'country' | 'continent';

/** Default grouping ladder: continent (zoom below 3) → country → pins at zoom 5+. */
export const DEFAULT_MAPS_GROUP_AREA: MapsGroupArea = 'continent';

/** The area pins are grouped into at this zoom, or null to show every pin. */
export function groupAreaAt(
  by: MapsGroupBy,
  area: MapsGroupArea,
  zoom: number,
  view: 'addresses' | 'coverage',
): MapsGroupArea | null {
  if (by === 'off' || view !== 'addresses' || zoom >= COUNTRY_CLUSTER_EXPAND_ZOOM) return null;
  return area === 'continent' && zoom < CONTINENT_CLUSTER_EXPAND_ZOOM ? 'continent' : 'country';
}

/** @deprecated use groupAreaAt */
export function shouldClusterPinsByCountry(
  enabled: boolean,
  zoom: number,
  view: 'addresses' | 'coverage',
): boolean {
  return groupAreaAt(enabled ? 'feed' : 'off', 'country', zoom, view) !== null;
}

const DEFAULT_CLUSTER_COLOR = '#2563eb';

/** What one badge of a country marker counts: each layer, or each layer feed. */
export type CountryClusterBy = 'layer' | 'feed';

export interface CountryClusterOptions {
  /** Layer title of a pin (badge tooltip in layer mode). */
  layerTitle?: (pin: MapsPinMarker) => string | undefined;
  groupBy?: CountryClusterBy;
  /** Country label points; without one a country sits at the mean of its pins. */
  centers?: CountryCenterIndex | null;
  /** Group into countries (default) or continents (countries without one stay alone). */
  area?: MapsGroupArea;
}

type ClusterBadge = NonNullable<MapsPinMarker['clusterLayers']>[number];

/**
 * Badges inside one country marker, in first-seen order: one per layer (its
 * color) or one per feed (the feed color, each site counted once even when it
 * sits in several of the feed's layers). Pins without a layer share one badge.
 */
export function countryClusterLayers(
  members: MapsPinMarker[],
  options: CountryClusterOptions | ((pin: MapsPinMarker) => string | undefined) = {},
): ClusterBadge[] {
  const { layerTitle, groupBy = 'layer' } = typeof options === 'function' ? { layerTitle: options } : options;
  const badges = new Map<string, ClusterBadge>();
  const seen = new Set<string>();
  for (const pin of members) {
    const byFeed = groupBy === 'feed';
    const key = (byFeed ? pin.feedId ?? pin.layerId : pin.layerId) ?? '';
    if (byFeed) {
      const site = `${key}:${pin.featureId ?? pin.id}`;
      if (seen.has(site)) continue;
      seen.add(site);
    }
    const badge = badges.get(key);
    if (badge) {
      badge.count += 1;
      continue;
    }
    badges.set(key, {
      layerId: key,
      title: byFeed ? pin.feedTitle ?? layerTitle?.(pin) : layerTitle?.(pin),
      color: (byFeed ? pin.feedColor : undefined) ?? pin.layerColor ?? pin.color ?? DEFAULT_CLUSTER_COLOR,
      count: 1,
    });
  }
  return [...badges.values()];
}

/**
 * One marker per country — on the country's label point when known — holding a
 * numbered badge per layer (or per feed) in its color. Every country with a
 * pin gets one, single sites included. Pins without `country` are unchanged.
 */
export function clusterPinsByCountry(
  pins: MapsPinMarker[],
  options: CountryClusterOptions | ((pin: MapsPinMarker) => string | undefined) = {},
): MapsPinMarker[] {
  const opts: CountryClusterOptions = typeof options === 'function' ? { layerTitle: options } : options;
  const byCountry = new Map<string, { label: string; center?: CountryCenter; members: MapsPinMarker[] }>();
  const withoutCountry: MapsPinMarker[] = [];

  for (const pin of pins) {
    const country = pin.country?.trim();
    if (!country) {
      withoutCountry.push(pin);
      continue;
    }
    // Feeds spell countries differently ("Brasil", "Brazil"): group on the matched country.
    const match = findCountryCenter(opts.centers, country);
    const continent =
      opts.area === 'continent' && match ? continentForGrouping(match) : null;
    const continentCenter = continent ? CONTINENT_CENTERS[continent] : undefined;
    const center: CountryCenter | undefined =
      continent && continentCenter ? { name: continent, ...continentCenter } : match;
    const key = continent
      ? `continent:${continent}`
      : match
        ? `ne:${match.name}`
        : `raw:${normalizeCountryName(country)}`;
    const group = byCountry.get(key) ?? { label: center?.name ?? country, center, members: [] };
    group.members.push(pin);
    byCountry.set(key, group);
  }

  const clustered: MapsPinMarker[] = [];
  for (const [key, { label, center, members }] of byCountry) {
    const lat = center?.lat ?? members.reduce((sum, p) => sum + p.lat, 0) / members.length;
    const lng = center?.lng ?? members.reduce((sum, p) => sum + p.lng, 0) / members.length;
    const layers = countryClusterLayers(members, opts);
    const total = layers.reduce((sum, layer) => sum + layer.count, 0);
    const detail =
      layers.length > 1 || layers[0]?.title
        ? layers.map((l) => `${l.count} ${l.title ?? 'locations'}`).join(' · ')
        : `${total} location${total === 1 ? '' : 's'}`;
    clustered.push({
      id: `country-cluster:${key}`,
      lat,
      lng,
      label,
      detail,
      country: key.startsWith('continent:') ? undefined : label,
      memberIds: members.map((p) => p.id),
      clusterCount: total,
      clusterLayers: layers,
      color: layers[0]?.color,
      size: 14,
    });
  }

  return [...clustered, ...withoutCountry];
}

export function resolveClusterMemberPins(
  cluster: MapsPinMarker,
  allPins: MapsPinMarker[],
): MapsPinMarker[] {
  if (!cluster.memberIds?.length) return [cluster];
  const byId = new Map(allPins.map((p) => [p.id, p]));
  return cluster.memberIds.map((id) => byId.get(id)).filter((p): p is MapsPinMarker => !!p);
}
