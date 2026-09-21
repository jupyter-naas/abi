export function parsePlacePhotoRef(raw: string | null): string | null {
  const ref = (raw ?? '').trim();
  if (!ref || ref.length > 512) return null;
  if (!/^[A-Za-z0-9_\-=.]+$/.test(ref)) return null;
  return ref;
}

export function placePhotoUpstreamUrl(ref: string, key: string, maxwidth = 800): string {
  const url = new URL('https://maps.googleapis.com/maps/api/place/photo');
  url.searchParams.set('photo_reference', ref);
  url.searchParams.set('maxwidth', String(maxwidth));
  url.searchParams.set('key', key);
  return url.toString();
}
