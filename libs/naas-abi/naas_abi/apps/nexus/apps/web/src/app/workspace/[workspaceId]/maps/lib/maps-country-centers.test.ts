import { describe, expect, it } from 'vitest';
import { buildCountryCenterIndex, findCountryCenter } from './maps-country-centers';
import type { NaturalEarthFeatureCollection } from './maps-natural-earth-basemap';

const country = (props: Record<string, unknown>) => ({
  type: 'Feature' as const,
  geometry: { type: 'Point' as const, coordinates: [0, 0] },
  properties: props,
});

const NE = {
  type: 'FeatureCollection',
  features: [
    country({ NAME: 'France', NAME_FR: 'France', NAME_DE: 'Frankreich', ISO_A2: 'FR', LABEL_X: 2.55, LABEL_Y: 46.7 }),
    country({ NAME: 'South Africa', NAME_FR: 'Afrique du Sud', LABEL_X: 23.6, LABEL_Y: -29.7 }),
    country({ NAME: 'China', NAME_FR: 'République populaire de Chine', LABEL_X: 106.3, LABEL_Y: 32.9 }),
    country({ NAME: 'Nowhere', LABEL_X: 'x' }),
  ],
} as unknown as NaturalEarthFeatureCollection;

describe('country centers', () => {
  const index = buildCountryCenterIndex(NE);

  it('matches any name, case and accents aside', () => {
    expect(findCountryCenter(index, 'Afrique du Sud')).toEqual({ name: 'South Africa', lat: -29.7, lng: 23.6 });
    expect(findCountryCenter(index, 'frankreich')?.name).toBe('France');
    expect(findCountryCenter(index, 'FR')?.name).toBe('France');
  });

  it('knows feed aliases and skips unknown countries', () => {
    expect(findCountryCenter(index, 'Chine')?.name).toBe('China');
    expect(findCountryCenter(index, 'Singapore')).toBeUndefined();
    expect(findCountryCenter(index, 'Nowhere')).toBeUndefined();
  });
});
