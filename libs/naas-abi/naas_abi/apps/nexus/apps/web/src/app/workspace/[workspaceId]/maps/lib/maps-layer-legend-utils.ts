import type { MapsPinMarker } from './leaflet-map';
import type { LayerLegendSublayer } from '../components/maps-active-layers-legend';
import { facilityClassIcon } from './maps-facility-class-symbology';

function normalizeHexColor(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed || !/^#[0-9a-f]{3,8}$/i.test(trimmed)) return undefined;
  return trimmed;
}

export function aggregateLayerLegendSublayers(
  pins: MapsPinMarker[],
  layerColor?: string,
): LayerLegendSublayer[] | undefined {
  const orgColor = normalizeHexColor(layerColor);
  const byLabel = new Map<string, number>();
  for (const pin of pins) {
    const label = pin.classLabel?.trim();
    if (!label) continue;
    byLabel.set(label, (byLabel.get(label) ?? 0) + 1);
  }
  if (byLabel.size <= 1) return undefined;
  return Array.from(byLabel, ([label, count]) => ({
    label,
    count,
    color: orgColor,
    icon: facilityClassIcon(label),
  })).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}
