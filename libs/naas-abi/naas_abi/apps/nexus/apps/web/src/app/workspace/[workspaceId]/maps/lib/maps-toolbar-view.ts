/** Human-readable map camera lines for the canvas toolbar. */

export function formatMapsToolbarCoord(value: number, axis: 'lat' | 'lng'): string {
  const abs = Math.abs(value);
  const hemi = axis === 'lat' ? (value >= 0 ? 'N' : 'S') : value >= 0 ? 'E' : 'W';
  return `${abs.toFixed(2)}°${hemi}`;
}

export function formatMapsToolbarCenter(lat: number, lng: number): string {
  return `${formatMapsToolbarCoord(lat, 'lat')}, ${formatMapsToolbarCoord(lng, 'lng')}`;
}

export function formatMapsToolbarZoom(zoom: number): string {
  return `Zoom ${Math.round(zoom)}`;
}

export function formatMapsToolbarViewLine(parts: {
  zoom: number;
  lat: number;
  lng: number;
  basemapLabel: string;
  radiusNm?: number;
}): string {
  const segments = [
    formatMapsToolbarZoom(parts.zoom),
    formatMapsToolbarCenter(parts.lat, parts.lng),
    parts.basemapLabel,
  ];
  if (parts.radiusNm != null && Number.isFinite(parts.radiusNm)) {
    segments.push(`~${Math.round(parts.radiusNm)} nm view`);
  }
  return segments.join(' · ');
}
