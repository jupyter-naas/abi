import { resolveGoogleMapsApiKey } from '../_google';
import { MAPS_USER_AGENT, mapsUpstreamGet } from '../_lib';

export type PlacePhoto = {
  url: string;
  label?: string;
  source: 'places' | 'streetview' | 'cited';
};

export type PlaceCard = {
  source: 'places' | 'streetview' | 'cited';
  keyed: boolean;
  name?: string;
  rating?: number;
  reviewCount?: number;
  category?: string;
  website?: string;
  phone?: string;
  address?: string;
  photos: PlacePhoto[];
};

export type PlaceQuery = {
  lat: number;
  lng: number;
  name: string;
  address: string;
  photo: string;
};

const SKIP_TYPES = new Set([
  'point_of_interest',
  'establishment',
  'political',
  'premise',
]);

export function parsePlaceQuery(params: URLSearchParams): PlaceQuery | null {
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
  const photo = (params.get('photo') ?? '').trim();
  return {
    lat,
    lng,
    name: (params.get('name') ?? '').trim().slice(0, 200),
    address: (params.get('address') ?? '').trim().slice(0, 300),
    photo: photo.startsWith('https://') ? photo : '',
  };
}

export function streetViewPreviewUrl(lat: number, lng: number): string {
  return `/api/maps/streetview?lat=${lat}&lng=${lng}&size=640x320`;
}

export function placePhotoProxyUrl(ref: string): string {
  return `/api/maps/place/photo?ref=${encodeURIComponent(ref)}`;
}

export function fallbackPlaceCard(query: PlaceQuery): PlaceCard {
  const photos: PlacePhoto[] = [];
  if (query.photo) {
    photos.push({ url: query.photo, label: 'Cited', source: 'cited' });
  }
  photos.push({
    url: streetViewPreviewUrl(query.lat, query.lng),
    label: 'Street View',
    source: 'streetview',
  });
  return {
    source: query.photo ? 'cited' : 'streetview',
    keyed: false,
    address: query.address || undefined,
    photos: photos.slice(0, 4),
  };
}

export function humanPlaceType(types: string[] | undefined): string | undefined {
  const first = (types ?? []).find((type) => !SKIP_TYPES.has(type));
  if (!first) return undefined;
  return first.replace(/_/g, ' ');
}

function findPlaceUrl(query: PlaceQuery, key: string): string {
  const input = [query.name, query.address].filter(Boolean).join(' ') || 'office';
  const url = new URL(
    'https://maps.googleapis.com/maps/api/place/findplacefromtext/json',
  );
  url.searchParams.set('input', input);
  url.searchParams.set('inputtype', 'textquery');
  url.searchParams.set('locationbias', `point:${query.lat},${query.lng}`);
  url.searchParams.set('fields', 'place_id,name,photos');
  url.searchParams.set('key', key);
  return url.toString();
}

function nearbySearchUrl(query: PlaceQuery, key: string): string {
  const url = new URL(
    'https://maps.googleapis.com/maps/api/place/nearbysearch/json',
  );
  url.searchParams.set('location', `${query.lat},${query.lng}`);
  url.searchParams.set('radius', '150');
  if (query.name) url.searchParams.set('keyword', query.name);
  url.searchParams.set('key', key);
  return url.toString();
}

function placeDetailsUrl(placeId: string, key: string): string {
  const url = new URL('https://maps.googleapis.com/maps/api/place/details/json');
  url.searchParams.set('place_id', placeId);
  url.searchParams.set(
    'fields',
    'name,rating,user_ratings_total,formatted_address,formatted_phone_number,international_phone_number,website,photos,types',
  );
  url.searchParams.set('key', key);
  return url.toString();
}

type PlacesPhoto = { photo_reference?: string };
type PlacesResult = {
  place_id?: string;
  name?: string;
  rating?: number;
  user_ratings_total?: number;
  formatted_address?: string;
  formatted_phone_number?: string;
  international_phone_number?: string;
  website?: string;
  types?: string[];
  photos?: PlacesPhoto[];
};

function photosFromPlace(photos: PlacesPhoto[] | undefined): PlacePhoto[] {
  return (photos ?? [])
    .map((photo) => photo.photo_reference)
    .filter((ref): ref is string => Boolean(ref && ref.length < 512))
    .slice(0, 4)
    .map((ref, index) => ({
      url: placePhotoProxyUrl(ref),
      label: index === 0 ? undefined : undefined,
      source: 'places' as const,
    }));
}

function cardFromPlace(place: PlacesResult, query: PlaceQuery): PlaceCard {
  const photos = photosFromPlace(place.photos);
  if (query.photo && !photos.some((photo) => photo.url === query.photo)) {
    photos.unshift({ url: query.photo, label: 'Cited', source: 'cited' });
  }
  if (photos.length === 0) {
    photos.push({
      url: streetViewPreviewUrl(query.lat, query.lng),
      label: 'Street View',
      source: 'streetview',
    });
  }
  const rating =
    typeof place.rating === 'number' && place.rating > 0 ? place.rating : undefined;
  const reviewCount =
    typeof place.user_ratings_total === 'number' && place.user_ratings_total > 0
      ? place.user_ratings_total
      : undefined;
  return {
    source: photos.some((photo) => photo.source === 'places') ? 'places' : 'streetview',
    keyed: true,
    name: place.name,
    rating,
    reviewCount,
    category: humanPlaceType(place.types),
    website: place.website?.startsWith('https://') ? place.website : undefined,
    phone: place.international_phone_number || place.formatted_phone_number,
    address: place.formatted_address || query.address || undefined,
    photos: photos.slice(0, 4),
  };
}

async function readPlacesJson(url: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await mapsUpstreamGet(url, {
      timeoutMs: 12000,
      headers: { Accept: 'application/json', 'User-Agent': MAPS_USER_AGENT },
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function lookupPlaceCard(
  query: PlaceQuery,
  env: NodeJS.ProcessEnv = process.env,
  fetchJson: (url: string) => Promise<Record<string, unknown> | null> = readPlacesJson,
): Promise<PlaceCard> {
  const resolved = resolveGoogleMapsApiKey(env);
  if (!resolved) return fallbackPlaceCard(query);

  const found = await fetchJson(findPlaceUrl(query, resolved.key));
  let placeId = (found?.candidates as PlacesResult[] | undefined)?.[0]?.place_id;
  if (!placeId) {
    const nearby = await fetchJson(nearbySearchUrl(query, resolved.key));
    placeId = (nearby?.results as PlacesResult[] | undefined)?.[0]?.place_id;
  }
  if (!placeId) return { ...fallbackPlaceCard(query), keyed: true };

  const details = await fetchJson(placeDetailsUrl(placeId, resolved.key));
  const place = (details?.result ?? details) as PlacesResult | undefined;
  if (!place || typeof place !== 'object') {
    return { ...fallbackPlaceCard(query), keyed: true };
  }
  return cardFromPlace(place, query);
}
