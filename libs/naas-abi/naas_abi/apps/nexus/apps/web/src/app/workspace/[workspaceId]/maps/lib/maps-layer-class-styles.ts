import type { MapsPinMarker } from './leaflet-map';

/** A pin's feature types: `classLabels` when it has several, else its `classLabel`. */
export function pinClassLabels(pin: MapsPinMarker): string[] {
  if (pin.classLabels?.length) return pin.classLabels;
  return pin.classLabel ? [pin.classLabel] : [];
}

/** A layer's slice of its feed: pins with one of its feature types; all when it lists none. */
export function layerFeedPins(
  pins: readonly MapsPinMarker[],
  classLabels: readonly string[] | undefined,
): MapsPinMarker[] {
  if (!classLabels?.length) return [...pins];
  const keep = new Set(classLabels);
  return pins.filter((pin) => pinClassLabels(pin).some((label) => keep.has(label)));
}

/**
 * A pin as drawn on the combined map: its layer's id prefix, color and icon. A
 * layer with its own icon shows it instead of the feed's logo.
 */
export function styleLayerPin(
  pin: MapsPinMarker,
  layer: {
    id: string;
    color: string;
    icon: string;
    ownIcon?: boolean;
    feed?: { id: string; color: string; title: string };
  },
): MapsPinMarker {
  return {
    ...pin,
    id: `${layer.id}:${pin.id}`,
    featureId: pin.id,
    layerId: layer.id,
    layerColor: layer.color,
    feedId: layer.feed?.id ?? layer.id,
    feedColor: layer.feed?.color ?? layer.color,
    feedTitle: layer.feed?.title,
    color: layer.color,
    markerIcon: layer.icon,
    ...(layer.ownIcon ? { markerLogoUrl: undefined } : {}),
  };
}

/** Feature types in a feed with their pin counts, most frequent first. */
export function collectClassLabels(pins: readonly MapsPinMarker[]): { label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const pin of pins) {
    for (const raw of pinClassLabels(pin)) {
      const label = raw.trim();
      if (label) counts.set(label, (counts.get(label) ?? 0) + 1);
    }
  }
  return [...counts]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}
