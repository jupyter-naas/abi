import type { MapsPinMarker } from './leaflet-map';
import { layerFeedPins } from './maps-layer-class-styles';
import type { LayoutEntry } from './layouts';

/** Pin totals for a feed row and each of its layer rows in the sidebar. */
export function layerCountsForFeedLoad(
  entries: readonly LayoutEntry[],
  feedKey: string,
  pins: readonly MapsPinMarker[],
): Record<string, number> {
  const counts: Record<string, number> = { [`feed:${feedKey}`]: pins.length };
  for (const entry of entries) {
    if ((entry.feedId ?? entry.id) === feedKey) {
      counts[entry.id] = layerFeedPins(pins, entry.classLabels).length;
    }
  }
  return counts;
}

/** Unique feed keys for combinable layout entries (one GeoJSON fetch per feed). */
export function combinableFeedKeys(entries: readonly LayoutEntry[]): string[] {
  const keys = new Set<string>();
  for (const entry of entries) {
    if (entry.combinable) keys.add(entry.feedId ?? entry.id);
  }
  return [...keys];
}
