import { describe, expect, it } from 'vitest';
import type { MapsPinMarker } from './leaflet-map';
import { collectClassLabels, layerFeedPins, styleLayerPin } from './maps-layer-class-styles';

const pin = (id: string, classLabel?: string): MapsPinMarker => ({
  id,
  lat: 0,
  lng: 0,
  label: id,
  classLabel,
  markerLogoUrl: '/api/organizations/logos/EDF/EDF.ico',
});

const FEED = [pin('1', 'Solar'), pin('2', 'Hydro'), pin('3', 'Hydro (planned)'), pin('4')];

describe('layerFeedPins', () => {
  it('keeps the layer feature types, or everything', () => {
    expect(layerFeedPins(FEED, ['Hydro', 'Hydro (planned)']).map((p) => p.id)).toEqual(['2', '3']);
    expect(layerFeedPins(FEED, []).map((p) => p.id)).toEqual(['1', '2', '3', '4']);
  });
});

describe('multi-type features', () => {
  it('belong to every layer of their types', () => {
    const site = { ...pin('v1'), classLabel: 'Division Power', classLabels: ['Division Power', 'Division Light'] };
    expect(layerFeedPins([site], ['Division Light'])).toHaveLength(1);
    expect(layerFeedPins([site], ['Division Brain'])).toHaveLength(0);
    expect(collectClassLabels([site, pin('v2', 'Division Light')])).toEqual([
      { label: 'Division Light', count: 2 },
      { label: 'Division Power', count: 1 },
    ]);
  });
});

describe('styleLayerPin', () => {
  it('prefixes, colors and labels pins with their layer', () => {
    expect(styleLayerPin(pin('1', 'Solar'), { id: 'edf-solar', color: '#e85130', icon: 'Sun', ownIcon: true })).toMatchObject({
      id: 'edf-solar:1',
      layerId: 'edf-solar',
      color: '#e85130',
      markerIcon: 'Sun',
      markerLogoUrl: undefined,
    });
    expect(styleLayerPin(pin('2'), { id: 'edf', color: '#001a70', icon: 'Zap' }).markerLogoUrl).toBe(
      '/api/organizations/logos/EDF/EDF.ico',
    );
  });
});

describe('collectClassLabels', () => {
  it('counts types, most frequent first', () => {
    expect(collectClassLabels([pin('a', 'Solar'), pin('b', 'Hydro'), pin('c', 'Solar'), pin('d')])).toEqual([
      { label: 'Solar', count: 2 },
      { label: 'Hydro', count: 1 },
    ]);
  });
});
