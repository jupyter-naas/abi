import type { MapsPinMarker } from './leaflet-map';

/**
 * Street View, image-search, and inspector card URLs for map pins.
 *
 * Street View uses the documented Google Maps URLs API (no API key, no Place FID):
 * https://developers.google.com/maps/documentation/urls/get-started#street-view-action
 *
 * Inspector photos come from `/api/maps/place` (Places Photo + Details when a
 * server key exists). Without a key the proxy returns Street View Static plus
 * any cited HTTPS `foaf:depiction`. Do not scrape Google Images or store JPGs.
 */

export function streetViewPanoUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}`;
}

export function streetViewFallbackUrl(lat: number, lng: number): string {
  const point = `${lat},${lng}`;
  return `https://www.google.com/maps?q=${point}&layer=c&cbll=${point}`;
}

export function directionsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
}

export function imageSearchUrl(query: string): string {
  return `https://www.google.com/search?tbm=isch&q=${encodeURIComponent(query)}`;
}

export function pinImageSearchQuery(pin: MapsPinMarker): string {
  const address = pin.address ?? pin.detail?.split('\n')[0] ?? '';
  return [pinOrganization(pin), pin.label, address].filter(Boolean).join(' ');
}

export function streetViewPreviewUrl(lat: number, lng: number): string {
  const params = new URLSearchParams({
    lat: String(lat),
    lng: String(lng),
    size: '640x320',
  });
  return `/api/maps/streetview?${params}`;
}

export function osmEmbedUrl(lat: number, lng: number): string {
  const pad = 0.0025;
  const bbox = [lng - pad, lat - pad, lng + pad, lat + pad].join(',');
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
}

export function pinOrganization(pin: MapsPinMarker): string | undefined {
  return pin.relationships?.find(
    (item) => item.label === 'Organization' || item.label === 'Address organization',
  )?.value;
}

export function pinCardTitle(pin: MapsPinMarker): string {
  return pinOrganization(pin) ?? pin.label;
}

export function pinCardCategory(pin: MapsPinMarker): string {
  return [pin.classLabel, pin.country || pin.label].filter(Boolean).join(' · ');
}

export function placeCardUrl(pin: MapsPinMarker): string {
  const params = new URLSearchParams({
    lat: String(pin.lat),
    lng: String(pin.lng),
    name: pinCardTitle(pin),
  });
  if (pin.address) params.set('address', pin.address);
  if (pin.photoUrl) params.set('photo', pin.photoUrl);
  return `/api/maps/place?${params}`;
}

export function resolvePinMedia(pin: MapsPinMarker): {
  photoUrl?: string;
  photoSource?: string;
  previewUrl: string;
  embedUrl: string;
  placeCardUrl: string;
  streetViewUrl: string;
  streetViewFallbackUrl: string;
  directionsUrl: string;
  imageSearchUrl: string;
  websiteUrl?: string;
  phone?: string;
  title: string;
  category: string;
} {
  return {
    photoUrl: pin.photoUrl,
    photoSource: pin.photoSource,
    previewUrl: streetViewPreviewUrl(pin.lat, pin.lng),
    embedUrl: osmEmbedUrl(pin.lat, pin.lng),
    placeCardUrl: placeCardUrl(pin),
    streetViewUrl: pin.streetViewUrl ?? streetViewPanoUrl(pin.lat, pin.lng),
    streetViewFallbackUrl: pin.streetViewFallbackUrl ?? streetViewFallbackUrl(pin.lat, pin.lng),
    directionsUrl: directionsUrl(pin.lat, pin.lng),
    imageSearchUrl: pin.imageSearchUrl ?? imageSearchUrl(pinImageSearchQuery(pin)),
    websiteUrl: pin.websiteUrl,
    phone: pin.phone,
    title: pinCardTitle(pin),
    category: pinCardCategory(pin),
  };
}
