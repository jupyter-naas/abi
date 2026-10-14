import { describe, expect, it } from 'vitest';
import type { CountryCenterRow } from '@/app/api/maps/country-centers/centers';
import { buildCountryCenterIndex } from './maps-country-centers';
import {
  continentsOnPins,
  pinMatchesRegionFilter,
} from './maps-pin-region';
import type { MapsPinMarker } from './leaflet-map';

const row = (name: string, continent: string): CountryCenterRow => ({
  name,
  names: [name],
  lat: 0,
  lng: 0,
  continent,
});

const pin = (country: string): MapsPinMarker => ({
  id: country,
  label: country,
  lat: 0,
  lng: 0,
  country,
});

describe('maps-pin-region', () => {
  const centers = buildCountryCenterIndex([
    row('France', 'Europe'),
    row('Japan', 'Asia'),
  ]);

  it('lists distinct continents from pins', () => {
    expect(
      continentsOnPins([pin('France'), pin('Japan'), pin('France')], centers),
    ).toEqual(['Asia', 'Europe']);
  });

  it('filters pins by continent set', () => {
    const filter = { mode: 'some' as const, regions: new Set(['Europe']) };
    expect(pinMatchesRegionFilter(pin('France'), filter, centers)).toBe(true);
    expect(pinMatchesRegionFilter(pin('Japan'), filter, centers)).toBe(false);
  });
});
