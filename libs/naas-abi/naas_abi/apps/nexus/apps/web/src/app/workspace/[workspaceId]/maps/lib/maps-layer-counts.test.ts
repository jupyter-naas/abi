import { describe, expect, it } from 'vitest';
import type { LayoutEntry } from './layouts';
import { combinableFeedKeys, layerCountsForFeedLoad } from './maps-layer-counts';
import type { MapsPinMarker } from './leaflet-map';

function entry(partial: Partial<LayoutEntry> & Pick<LayoutEntry, 'id'>): LayoutEntry {
  return {
    title: partial.id,
    kind: 'feed',
    combinable: true,
    icon: 'MapPin',
    ...partial,
  } as LayoutEntry;
}

const pin = (id: string, classLabel?: string): MapsPinMarker =>
  ({ id, lat: 0, lng: 0, label: id, classLabel }) as MapsPinMarker;

describe('layerCountsForFeedLoad', () => {
  it('counts feed total and per-layer slices', () => {
    const entries = [
      entry({ id: 'a-hq', feedId: 'a-facilities', classLabels: ['Headquarters'] }),
      entry({ id: 'a-off', feedId: 'a-facilities', classLabels: ['Office'] }),
    ];
    const pins = [
      pin('1', 'Headquarters'),
      pin('2', 'Office'),
      pin('3', 'Office'),
    ];
    expect(layerCountsForFeedLoad(entries, 'a-facilities', pins)).toEqual({
      'feed:a-facilities': 3,
      'a-hq': 1,
      'a-off': 2,
    });
  });
});

describe('combinableFeedKeys', () => {
  it('dedupes by feedId', () => {
    const entries = [
      entry({ id: 'x-one', feedId: 'feed-x' }),
      entry({ id: 'x-two', feedId: 'feed-x' }),
    ];
    expect(combinableFeedKeys(entries)).toEqual(['feed-x']);
  });
});
