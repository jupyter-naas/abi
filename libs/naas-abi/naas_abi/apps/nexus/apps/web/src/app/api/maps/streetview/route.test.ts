import { NextRequest } from 'next/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { resolveGoogleMapsApiKey } from '../_google';
import { GET } from './route';
import {
  googleStreetViewStaticUrl,
  lonLatToTile,
  osmTileUrl,
  parseStreetViewQuery,
  placeholderPreviewSvg,
} from './streetview';

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.GOOGLE_MAPS_API_KEY;
  delete process.env.MAPS_API_KEY;
  delete process.env.GOOGLE_API_KEY;
});

describe('streetview query', () => {
  it('requires a real coordinate and caps size', () => {
    expect(parseStreetViewQuery(new URLSearchParams())).toBeNull();
    expect(parseStreetViewQuery(new URLSearchParams('lat=999&lng=0'))).toBeNull();
    expect(parseStreetViewQuery(new URLSearchParams('lat=38.9&lng=-77.06'))).toEqual({
      lat: 38.9,
      lng: -77.06,
      width: 640,
      height: 320,
    });
    expect(
      parseStreetViewQuery(new URLSearchParams('lat=1&lng=2&size=2400x80')),
    ).toEqual({ lat: 1, lng: 2, width: 640, height: 80 });
  });

  it('reads a server Maps key and ignores placeholders', () => {
    expect(resolveGoogleMapsApiKey({})).toBeNull();
    expect(resolveGoogleMapsApiKey({ GOOGLE_MAPS_API_KEY: 'changeme' })).toBeNull();
    expect(
      resolveGoogleMapsApiKey({ GOOGLE_API_KEY: 'AIzaSyPlaceholderKey99' }),
    ).toEqual({ key: 'AIzaSyPlaceholderKey99', name: 'GOOGLE_API_KEY' });
    expect(
      resolveGoogleMapsApiKey({
        GOOGLE_PLACES_API_KEY: 'places-server-key-123456',
        GOOGLE_MAPS_API_KEY: 'maps-server-key-123456',
        GOOGLE_API_KEY: 'gemini-should-lose',
      }),
    ).toEqual({ key: 'places-server-key-123456', name: 'GOOGLE_PLACES_API_KEY' });
  });

  it('builds Street View Static and OSM tile URLs without Place FIDs', () => {
    const url = googleStreetViewStaticUrl(
      { lat: 38.9031704, lng: -77.0598347, width: 640, height: 320 },
      'maps-server-key-123456',
    );
    expect(url).toContain('maps.googleapis.com/maps/api/streetview');
    expect(url).toContain('location=38.9031704%2C-77.0598347');
    expect(url).not.toContain('fid');
    expect(url).not.toContain('panoid');
    const tile = lonLatToTile(38.9031704, -77.0598347, 17);
    expect(osmTileUrl(17, tile.x, tile.y)).toBe(
      `https://tile.openstreetmap.org/17/${tile.x}/${tile.y}.png`,
    );
    expect(placeholderPreviewSvg({ lat: 1, lng: 2, width: 64, height: 32 }, 'Location preview')).toContain(
      'Location preview',
    );
  });

  it('proxies an OSM preview when no server key is set', async () => {
    const png = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
      'base64',
    );
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: async () =>
          png.buffer.slice(png.byteOffset, png.byteOffset + png.byteLength),
      }),
    );
    const res = await GET(
      new NextRequest('http://localhost/api/maps/streetview?lat=38.9031704&lng=-77.0598347'),
    );
    expect(res.status).toBe(200);
    expect(res.headers.get('X-Maps-Preview-Source')).toBe('openstreetmap');
    expect(res.headers.get('Content-Type')).toContain('image/svg+xml');
    expect(await res.text()).toContain('data:image/png;base64');
  });
});
