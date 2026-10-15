import type { MapsPinMarker } from './leaflet-map';

export function pinSearchHaystack(pin: MapsPinMarker): string {
  return [pin.label, pin.country, pin.detail, pin.address, pin.classLabel]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

/** Case-insensitive substring match across label, country, detail, address, class. */
export function searchMapPins(
  pins: readonly MapsPinMarker[],
  query: string,
  limit = 10,
): MapsPinMarker[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const out: MapsPinMarker[] = [];
  for (const pin of pins) {
    if (pinSearchHaystack(pin).includes(q)) {
      out.push(pin);
      if (out.length >= limit) break;
    }
  }
  return out;
}
