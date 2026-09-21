/** In-memory AIS vessel cache. No I/O. Process-local to the Node Maps runtime. */

export const AIS_PIN_LIMIT = 400;
export const AIS_STALE_MS = 30 * 60 * 1000;
export const AIS_CACHE_MAX = 20_000;

export interface AisBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface AisVessel {
  mmsi: string;
  lat: number;
  lng: number;
  name: string;
  sog?: number;
  cog?: number;
  heading?: number;
  destination?: string;
  updatedAt: number;
  observedAt?: string;
}

export type AisEnvelope = {
  error?: unknown;
  MessageType?: string;
  Message?: Record<string, Record<string, unknown>>;
  MetaData?: Record<string, unknown>;
  Metadata?: Record<string, unknown>;
};

const POSITION_TYPES = new Set([
  'PositionReport',
  'StandardClassBPositionReport',
  'ExtendedClassBPositionReport',
  'AidsToNavigationReport',
  'BaseStationReport',
  'StandardClassBCSPositionReport',
]);

function finiteNumber(value: unknown): number | undefined {
  if (value == null || value === '') return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function text(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.replace(/@+$/g, '').trim();
  return trimmed || undefined;
}

function mmsiOf(envelope: AisEnvelope, body: Record<string, unknown>): string | null {
  const metadata = envelope.MetaData ?? envelope.Metadata ?? {};
  const raw =
    metadata.MMSI ??
    metadata.mmsi ??
    body.UserID ??
    body.UserId ??
    body.Mmsi;
  const mmsi = String(raw ?? '').trim();
  return /^\d{5,10}$/.test(mmsi) ? mmsi : null;
}

export function parseAisFrame(textFrame: string):
  | { kind: 'malformed' }
  | { kind: 'error'; message: string }
  | { kind: 'data'; envelope: AisEnvelope } {
  let envelope: AisEnvelope;
  try {
    envelope = JSON.parse(textFrame) as AisEnvelope;
  } catch {
    return { kind: 'malformed' };
  }
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) {
    return { kind: 'malformed' };
  }
  if (envelope.error) return { kind: 'error', message: String(envelope.error) };
  return { kind: 'data', envelope };
}

export function ingestAisEnvelope(
  vessels: Map<string, AisVessel>,
  envelope: AisEnvelope,
  now = Date.now(),
): boolean {
  const messageType = envelope.MessageType;
  if (typeof messageType !== 'string') return false;
  const body = envelope.Message?.[messageType];
  if (!body || typeof body !== 'object') return false;
  const mmsi = mmsiOf(envelope, body);
  if (!mmsi) return false;

  const metadata = envelope.MetaData ?? envelope.Metadata ?? {};
  const lat = finiteNumber(metadata.latitude ?? metadata.Latitude ?? body.Latitude);
  const lng = finiteNumber(metadata.longitude ?? metadata.Longitude ?? body.Longitude);
  const existing = vessels.get(mmsi);
  const name =
    text(metadata.ShipName ?? metadata.shipName) ||
    text(body.Name) ||
    existing?.name ||
    `MMSI ${mmsi}`;

  if (lat == null || lng == null || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
    if (existing && (text(body.Destination) || text(body.Name))) {
      vessels.set(mmsi, {
        ...existing,
        name,
        destination: text(body.Destination) ?? existing.destination,
        updatedAt: now,
      });
      return true;
    }
    return POSITION_TYPES.has(messageType) ? false : true;
  }

  const observedAt = text(metadata.time_utc ?? metadata.TimeUtc);
  vessels.set(mmsi, {
    mmsi,
    lat,
    lng,
    name,
    sog: finiteNumber(body.Sog ?? body.SOG) ?? existing?.sog,
    cog: finiteNumber(body.Cog ?? body.COG) ?? existing?.cog,
    heading: finiteNumber(body.TrueHeading ?? body.Heading) ?? existing?.heading,
    destination: text(body.Destination) ?? existing?.destination,
    updatedAt: now,
    observedAt: observedAt && Number.isFinite(Date.parse(observedAt))
      ? new Date(Date.parse(observedAt)).toISOString()
      : new Date(now).toISOString(),
  });
  pruneAisVessels(vessels, now);
  return true;
}

export function pruneAisVessels(vessels: Map<string, AisVessel>, now = Date.now()): void {
  for (const [mmsi, vessel] of vessels) {
    if (now - vessel.updatedAt > AIS_STALE_MS) vessels.delete(mmsi);
  }
  if (vessels.size <= AIS_CACHE_MAX) return;
  const ranked = [...vessels.values()].sort((a, b) => a.updatedAt - b.updatedAt);
  const drop = ranked.length - AIS_CACHE_MAX;
  for (let i = 0; i < drop; i += 1) vessels.delete(ranked[i].mmsi);
}

export function inAisBounds(lat: number, lng: number, bounds: AisBounds): boolean {
  if (lat < bounds.south || lat > bounds.north) return false;
  if (bounds.west <= bounds.east) {
    return lng >= bounds.west && lng <= bounds.east;
  }
  return lng >= bounds.west || lng <= bounds.east;
}

export function parseAisBounds(searchParams: URLSearchParams): AisBounds | null {
  const west = Number(searchParams.get('west'));
  const south = Number(searchParams.get('south'));
  const east = Number(searchParams.get('east'));
  const north = Number(searchParams.get('north'));
  if (![west, south, east, north].every(Number.isFinite)) return null;
  if (Math.abs(south) > 90 || Math.abs(north) > 90 || south > north) return null;
  if (Math.abs(west) > 180 || Math.abs(east) > 180) return null;
  return { west, south, east, north };
}

export function vesselsInView(
  vessels: Map<string, AisVessel>,
  bounds: AisBounds | null,
  limit = AIS_PIN_LIMIT,
  now = Date.now(),
): AisVessel[] {
  const fresh = [...vessels.values()]
    .filter((v) => now - v.updatedAt <= AIS_STALE_MS)
    .filter((v) => (bounds ? inAisBounds(v.lat, v.lng, bounds) : true))
    .sort((a, b) => b.updatedAt - a.updatedAt);
  return fresh.slice(0, limit);
}

export function aisVesselsToPins(rows: AisVessel[]): Array<Record<string, unknown>> {
  return rows.map((row) => {
    const kn = row.sog != null ? `${row.sog.toFixed(1)} kn` : '';
    const dest = row.destination ? ` → ${row.destination}` : '';
    const detail = [kn, dest, 'AISStream'].filter(Boolean).join(' · ');
    return {
      id: row.mmsi,
      lat: row.lat,
      lng: row.lng,
      label: row.name,
      detail,
      color: '#0f766e',
      size: 8,
      observedAt: row.observedAt,
      sources: [{ title: 'AISStream', url: 'https://aisstream.io/' }],
    };
  });
}
