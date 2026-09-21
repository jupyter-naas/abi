import { describe, expect, it } from 'vitest';
import {
  directionsUrl,
  imageSearchUrl,
  resolvePinMedia,
  streetViewFallbackUrl,
  streetViewPanoUrl,
  streetViewPreviewUrl,
} from './maps-pin-media';

describe('pin media URLs', () => {
  it('builds Street View from viewpoint coordinates, never a Place FID', () => {
    expect(streetViewPanoUrl(38.9031704, -77.0598347)).toBe(
      'https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=38.9031704,-77.0598347',
    );
    expect(streetViewFallbackUrl(38.9031704, -77.0598347)).toBe(
      'https://www.google.com/maps?q=38.9031704,-77.0598347&layer=c&cbll=38.9031704,-77.0598347',
    );
    expect(directionsUrl(38.9031704, -77.0598347)).toContain('destination=38.9031704,-77.0598347');
    expect(streetViewPanoUrl(38.9, -77.06)).not.toContain('fid');
    expect(streetViewPanoUrl(38.9, -77.06)).not.toContain('panoid');
  });

  it('builds a same-origin place card and prefers a cited photo', () => {
    expect(imageSearchUrl('Palantir 1025 Thomas Jefferson Street NW')).toContain('tbm=isch');
    expect(streetViewPreviewUrl(38.9031704, -77.0598347)).toBe(
      '/api/maps/streetview?lat=38.9031704&lng=-77.0598347&size=640x320',
    );
    const media = resolvePinMedia({
      id: 'dc',
      lat: 38.9031704,
      lng: -77.0598347,
      label: 'Washington, DC',
      address: '1025 Thomas Jefferson Street NW, Suite 600, Washington, DC 20007, United States',
      relationships: [{ label: 'Organization', value: 'Palantir Technologies Inc.' }],
    });
    expect(media.title).toBe('Palantir Technologies Inc.');
    expect(media.streetViewUrl).toContain('map_action=pano');
    expect(media.imageSearchUrl).toContain('Thomas');
    expect(media.photoUrl).toBeUndefined();
    expect(media.previewUrl).toContain('/api/maps/streetview');
    expect(media.placeCardUrl).toContain('/api/maps/place?');
    expect(media.placeCardUrl).toContain('Palantir');
    expect(
      resolvePinMedia({
        id: 'dc',
        lat: 1,
        lng: 2,
        label: 'Office',
        photoUrl: 'https://upload.wikimedia.org/photo.jpg',
      }).photoUrl,
    ).toBe('https://upload.wikimedia.org/photo.jpg');
  });
});
