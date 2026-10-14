import { describe, expect, it } from 'vitest';
import { buildCountryCenterIndex } from './maps-country-centers';
import type { CountryCenterRow } from '@/app/api/maps/country-centers/centers';
import {
  facilityCountsByRegionAndFeed,
  basemapRegionOverlay,
  regionForCountry,
  showMapRegionLabelsAtZoom,
} from './maps-map-regions';
import type { MapsPinMarker } from './leaflet-map';

const countryToRegion = {
  France: 'europe',
  Peru: 'americas',
};

function pin(partial: Partial<MapsPinMarker> & Pick<MapsPinMarker, 'id'>): MapsPinMarker {
  return {
    lat: 0,
    lng: 0,
    label: partial.id,
    ...partial,
  };
}

describe('showMapRegionLabelsAtZoom', () => {
  it('hides labels from zoom 3 upward', () => {
    expect(showMapRegionLabelsAtZoom(2)).toBe(true);
    expect(showMapRegionLabelsAtZoom(3)).toBe(false);
    expect(showMapRegionLabelsAtZoom(5)).toBe(false);
  });
});

describe('basemapRegionOverlay', () => {
  it('reads the regions and their countries from a basemap renderer', () => {
    const overlay = basemapRegionOverlay({
      kind: 'countries',
      regions: [
        { id: 'europe', name: 'Europe', label_x: 0.4, label_y: 0.1, color: '#171c8f', countries: ['France'] },
        { id: 'americas', name: 'Americas', label_x: 0.1, label_y: 0.4, color: '#0072ce', countries: ['Peru'] },
      ],
    });
    expect(overlay?.regions.map((r) => [r.id, r.labelX])).toEqual([['europe', 0.4], ['americas', 0.1]]);
    expect(overlay?.countryToRegion).toEqual(countryToRegion);
  });

  it('is undefined for a basemap without regions', () => {
    expect(basemapRegionOverlay({ kind: 'countries' })).toBeUndefined();
    expect(basemapRegionOverlay({ kind: 'tile', url: 'https://t/{z}/{x}/{y}.png' })).toBeUndefined();
    expect(basemapRegionOverlay(undefined)).toBeUndefined();
  });
});

const centerRows: CountryCenterRow[] = [
  { name: 'China', names: ['Chine'], lat: 35, lng: 105, continent: 'Asia' },
  { name: 'Brazil', names: ['Brésil'], lat: -10, lng: -55, continent: 'South America' },
  { name: 'Germany', names: ['Allemagne'], lat: 51, lng: 10, continent: 'Europe' },
];
const centers = buildCountryCenterIndex(centerRows);

describe('regionForCountry with feed spellings', () => {
  it('maps French country labels via country centers', () => {
    expect(regionForCountry('Chine', countryToRegion, centers)).toBe(undefined);
    const extended = { ...countryToRegion, China: 'asia_pacific', Brazil: 'americas', Germany: 'europe' };
    expect(regionForCountry('Chine', extended, centers)).toBe('asia_pacific');
    expect(regionForCountry('Brésil', extended, centers)).toBe('americas');
  });
});

describe('facilityCountsByRegionAndFeed', () => {
  it('groups counts by region and feed', () => {
    const pins = [
      pin({
        id: '1',
        country: 'France',
        feedId: 'alpha-facilities',
        feedTitle: 'Alpha Org',
      }),
      pin({
        id: '2',
        country: 'France',
        feedId: 'alpha-facilities',
        feedTitle: 'Alpha Org',
      }),
      pin({ id: '3', country: 'Peru', feedId: 'alpha-facilities', feedTitle: 'Alpha Org' }),
      pin({ id: '4', country: 'France', feedId: 'beta-facilities', feedTitle: 'Beta Org' }),
    ];
    const byRegion = facilityCountsByRegionAndFeed(pins, countryToRegion);
    expect(byRegion.get('europe')).toEqual([
      { feedId: 'alpha-facilities', label: 'Alpha Org', count: 2 },
      { feedId: 'beta-facilities', label: 'Beta Org', count: 1 },
    ]);
    expect(byRegion.get('americas')).toEqual([
      { feedId: 'alpha-facilities', label: 'Alpha Org', count: 1 },
    ]);
  });
});

describe('regionForCountry', () => {
  it('resolves case-insensitive country names', () => {
    expect(regionForCountry('peru', countryToRegion)).toBe('americas');
  });
});
