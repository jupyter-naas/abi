const DEFAULT_SIZE = { width: 640, height: 320 };
const MAX_SIZE = { width: 640, height: 640 };
export const OSM_ZOOM = 17;

export type StreetViewQuery = {
  lat: number;
  lng: number;
  width: number;
  height: number;
};

export function parseStreetViewQuery(
  params: URLSearchParams,
): StreetViewQuery | null {
  if (!params.has('lat') || !params.has('lng')) return null;
  const lat = Number(params.get('lat'));
  const lng = Number(params.get('lng'));
  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng) ||
    Math.abs(lat) > 90 ||
    Math.abs(lng) > 180
  ) {
    return null;
  }
  const raw = params.get('size') ?? '';
  const match = /^(\d{2,4})x(\d{2,4})$/.exec(raw);
  const width = match
    ? Math.min(MAX_SIZE.width, Math.max(64, Number(match[1])))
    : DEFAULT_SIZE.width;
  const height = match
    ? Math.min(MAX_SIZE.height, Math.max(64, Number(match[2])))
    : DEFAULT_SIZE.height;
  return { lat, lng, width, height };
}

export function googleStreetViewStaticUrl(
  query: StreetViewQuery,
  key: string,
): string {
  const url = new URL('https://maps.googleapis.com/maps/api/streetview');
  url.searchParams.set('size', `${query.width}x${query.height}`);
  url.searchParams.set('location', `${query.lat},${query.lng}`);
  url.searchParams.set('fov', '80');
  url.searchParams.set('pitch', '0');
  url.searchParams.set('key', key);
  return url.toString();
}

export function lonLatToTile(
  lat: number,
  lng: number,
  zoom: number,
): { x: number; y: number; px: number; py: number } {
  const n = 2 ** zoom;
  const x = ((lng + 180) / 360) * n;
  const latRad = (lat * Math.PI) / 180;
  const y =
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) *
    n;
  return {
    x: Math.floor(x),
    y: Math.floor(y),
    px: (x - Math.floor(x)) * 256,
    py: (y - Math.floor(y)) * 256,
  };
}

export function osmTileUrl(zoom: number, x: number, y: number): string {
  const n = 2 ** zoom;
  const wrappedX = ((x % n) + n) % n;
  const clampedY = Math.min(n - 1, Math.max(0, y));
  return `https://tile.openstreetmap.org/${zoom}/${wrappedX}/${clampedY}.png`;
}

export function placeholderPreviewSvg(
  query: StreetViewQuery,
  reason: string,
): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${query.width}" height="${query.height}" viewBox="0 0 ${query.width} ${query.height}" role="img">
  <rect width="100%" height="100%" fill="#c5d0d8"/>
  <circle cx="${query.width / 2}" cy="${query.height / 2}" r="10" fill="#2563eb" stroke="#ffffff" stroke-width="3"/>
  <text x="50%" y="78%" text-anchor="middle" font-size="12" fill="#334155">${escapeXml(reason)}</text>
</svg>`;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
