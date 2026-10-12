import type { MapsPinMarker } from './leaflet-map';
import type { LayerLegendSublayer } from '../components/maps-active-layers-legend';

export function aggregateLayerLegendSublayers(
  pins: MapsPinMarker[],
): LayerLegendSublayer[] | undefined {
  const counts = new Map<string, number>();
  for (const pin of pins) {
    const label = pin.classLabel?.trim();
    if (!label) continue;
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  if (counts.size <= 1) return undefined;
  return Array.from(counts, ([label, count]) => ({ label, count })).sort(
    (a, b) => b.count - a.count || a.label.localeCompare(b.label),
  );
}
