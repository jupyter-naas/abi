import { describe, expect, it } from 'vitest';

import {
  hasMapsLayerChoice,
  mapsLayerPath,
  mapsLibraryPath,
  mapsPath,
  mapsSettingsPath,
  mapsSettingsSelectedFeed,
  mapsSettingsSelectedLayer,
  parseMapsLayerIds,
  parseMapsRoute,
} from './maps-route';

const WS = 'ws-1';
const BASE = `/workspace/${WS}/maps`;

describe('parseMapsLayerIds', () => {
  it('reads repeated layer params', () => {
    expect(parseMapsLayerIds('layer=earthquakes&layer=temperature')).toEqual([
      'earthquakes',
      'temperature',
    ]);
  });

  it('dedupes layer ids', () => {
    expect(parseMapsLayerIds('layer=iss&layer=iss')).toEqual(['iss']);
  });
});

describe('parseMapsRoute', () => {
  it('shows the library on the bare maps route', () => {
    expect(parseMapsRoute(BASE)).toEqual({
      isMapsRoute: true,
      layerIds: [],
      isMapView: false,
      isDataset: false,
      datasetId: null,
    });
  });

  it('opens the map when layer params are present', () => {
    expect(parseMapsRoute(BASE, 'layer=iss')).toEqual({
      isMapsRoute: true,
      layerIds: ['iss'],
      isMapView: true,
      isDataset: true,
      datasetId: 'iss',
    });
  });

  it('supports multiple layers', () => {
    expect(parseMapsRoute(BASE, 'layer=earthquakes&layer=temperature').layerIds).toEqual([
      'earthquakes',
      'temperature',
    ]);
  });

  it('does not claim routes that merely contain the word maps', () => {
    expect(parseMapsRoute(`/workspace/${WS}/chat`).isMapsRoute).toBe(false);
    expect(parseMapsRoute(`/workspace/${WS}/mapshare`).isMapsRoute).toBe(false);
    expect(parseMapsRoute(`/workspace/${WS}/settings/maps`).isMapsRoute).toBe(false);
  });
});

describe('mapsPath', () => {
  it('builds layer query strings', () => {
    expect(mapsLayerPath(WS, 'iss')).toBe(`${BASE}?layer=iss`);
    expect(mapsPath(WS, ['earthquakes', 'temperature'])).toBe(
      `${BASE}?layer=earthquakes&layer=temperature`,
    );
    expect(mapsPath(WS, [])).toBe(BASE);
  });

  it('keeps an explicit "no layers" choice so defaults are not applied again', () => {
    const none = mapsPath(WS, [], { explicit: true });
    expect(none).toBe(`${BASE}?layer=`);
    expect(parseMapsLayerIds(none.split('?')[1])).toEqual([]);
    expect(hasMapsLayerChoice(none.split('?')[1])).toBe(true);
    expect(hasMapsLayerChoice('')).toBe(false);
    expect(hasMapsLayerChoice('?layer=iss')).toBe(true);
    expect(mapsPath(WS, ['iss'], { explicit: true })).toBe(`${BASE}?layer=iss`);
  });

  it('degrades before a workspace is known', () => {
    expect(mapsLayerPath(null, 'earthquakes')).toBe('/maps?layer=earthquakes');
  });
});

describe('mapsLibraryPath', () => {
  it('points at the maps library inside the workspace', () => {
    expect(mapsLibraryPath(WS)).toBe(BASE);
  });
});

describe('mapsSettingsPath', () => {
  it('builds Settings → Maps paths', () => {
    expect(mapsSettingsPath('ws-1')).toBe('/workspace/ws-1/settings/maps');
    expect(mapsSettingsPath('ws-1', { create: true })).toBe('/workspace/ws-1/settings/maps?layer=new');
    expect(mapsSettingsPath('ws-1', { layer: 'offices' })).toBe(
      '/workspace/ws-1/settings/maps?layer=offices',
    );
  });

  it('builds feed and new-layer paths', () => {
    expect(mapsSettingsPath('ws-1', { feed: 'edf' })).toBe('/workspace/ws-1/settings/maps?feed=edf');
    expect(mapsSettingsPath('ws-1', { layer: 'new', forFeed: 'edf' })).toBe(
      '/workspace/ws-1/settings/maps?layer=new&for=edf',
    );
    expect(mapsSettingsSelectedFeed(new URLSearchParams('feed=edf'))).toBe('edf');
  });

  it('reads the selected layer, including older ?layout= links', () => {
    expect(mapsSettingsSelectedLayer(new URLSearchParams('layer=edf'))).toBe('edf');
    expect(mapsSettingsSelectedLayer(new URLSearchParams('layout=edf'))).toBe('edf');
    expect(mapsSettingsSelectedLayer(new URLSearchParams(''))).toBeNull();
  });
});
