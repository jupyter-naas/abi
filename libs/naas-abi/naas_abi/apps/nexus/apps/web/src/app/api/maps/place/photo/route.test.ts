import { describe, expect, it } from 'vitest';
import { parsePlacePhotoRef, placePhotoUpstreamUrl } from './route';

describe('place photo proxy', () => {
  it('accepts a photo reference and keeps the key on the server URL', () => {
    expect(parsePlacePhotoRef('')).toBeNull();
    expect(parsePlacePhotoRef('abc/../secret')).toBeNull();
    expect(parsePlacePhotoRef('abc-photo_1')).toBe('abc-photo_1');
    const url = placePhotoUpstreamUrl('abc-photo_1', 'places-server-key-123456');
    expect(url).toContain('maps.googleapis.com/maps/api/place/photo');
    expect(url).toContain('photo_reference=abc-photo_1');
  });
});
