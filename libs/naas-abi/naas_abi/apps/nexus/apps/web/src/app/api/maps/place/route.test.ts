import { describe, expect, it } from 'vitest';
import {
  fallbackPlaceCard,
  humanPlaceType,
  lookupPlaceCard,
  parsePlaceQuery,
  placePhotoProxyUrl,
} from './route';

describe('place card', () => {
  it('requires coordinates and keeps a cited photo in the keyless fallback', () => {
    expect(parsePlaceQuery(new URLSearchParams())).toBeNull();
    const query = parsePlaceQuery(
      new URLSearchParams(
        'lat=38.9031704&lng=-77.0598347&name=Palantir&address=1025%20Thomas%20Jefferson&photo=https://upload.wikimedia.org/office.jpg',
      ),
    );
    expect(query).toMatchObject({ lat: 38.9031704, lng: -77.0598347, name: 'Palantir' });
    const card = fallbackPlaceCard(query!);
    expect(card.source).toBe('cited');
    expect(card.keyed).toBe(false);
    expect(card.photos[0]).toEqual({
      url: 'https://upload.wikimedia.org/office.jpg',
      label: 'Cited',
      source: 'cited',
    });
    expect(card.photos[1].url).toContain('/api/maps/streetview');
    expect(humanPlaceType(['establishment', 'software_company'])).toBe('software company');
  });

  it('returns Place Photo proxy URLs when a key and details are available', async () => {
    const query = parsePlaceQuery(
      new URLSearchParams('lat=38.9&lng=-77.06&name=Palantir'),
    )!;
    const card = await lookupPlaceCard(
      query,
      { GOOGLE_PLACES_API_KEY: 'places-server-key-123456' },
      async (url) => {
        if (url.includes('findplacefromtext')) {
          return { candidates: [{ place_id: 'ChIJdc' }] };
        }
        return {
          result: {
            name: 'Palantir Technologies',
            rating: 4.1,
            user_ratings_total: 68,
            formatted_address: '1025 Thomas Jefferson Street NW',
            website: 'https://www.palantir.com',
            types: ['software_company'],
            photos: [{ photo_reference: 'abc-photo-1' }, { photo_reference: 'abc-photo-2' }],
          },
        };
      },
    );
    expect(card.source).toBe('places');
    expect(card.keyed).toBe(true);
    expect(card.rating).toBe(4.1);
    expect(card.website).toBe('https://www.palantir.com');
    expect(card.photos).toHaveLength(2);
    expect(card.photos[0].url).toBe(placePhotoProxyUrl('abc-photo-1'));
    expect(card.photos[0].source).toBe('places');
  });
});
