import { describe, expect, it } from 'vitest';

import {
  mapsDatasetPath,
  mapsLibraryPath,
  parseMapsRoute,
} from './maps-route';

const WS = 'ws-1';
const BASE = `/workspace/${WS}/maps`;

describe('parseMapsRoute', () => {
  it('shows the dataset library on the bare maps route', () => {
    expect(parseMapsRoute(BASE)).toEqual({
      isMapsRoute: true,
      isDataset: false,
      datasetId: null,
    });
  });

  it('opens a dataset canvas on /maps/{datasetId}', () => {
    expect(parseMapsRoute(`${BASE}/presence`)).toEqual({
      isMapsRoute: true,
      isDataset: true,
      datasetId: 'presence',
    });
  });

  it('opens earthquakes on /maps/earthquakes', () => {
    expect(parseMapsRoute(`${BASE}/earthquakes`)).toEqual({
      isMapsRoute: true,
      isDataset: true,
      datasetId: 'earthquakes',
    });
  });

  it('ignores a trailing slash on the index', () => {
    expect(parseMapsRoute(`${BASE}/`).isDataset).toBe(false);
    expect(parseMapsRoute(`${BASE}/presence/`).isDataset).toBe(true);
  });

  it('stops at a query string or fragment', () => {
    expect(parseMapsRoute(`${BASE}/presence?zoom=4`).isDataset).toBe(true);
    expect(parseMapsRoute(`${BASE}/presence#pin`).datasetId).toBe('presence');
  });

  it('does not claim routes that merely contain the word maps', () => {
    expect(parseMapsRoute(`/workspace/${WS}/chat`).isMapsRoute).toBe(false);
    expect(parseMapsRoute(`/workspace/${WS}/mapshare`).isMapsRoute).toBe(false);
  });

  it('treats a missing pathname as no route at all', () => {
    expect(parseMapsRoute(null).isMapsRoute).toBe(false);
    expect(parseMapsRoute(undefined).isMapsRoute).toBe(false);
  });
});

describe('mapsDatasetPath', () => {
  it('points at the dataset detail inside the workspace', () => {
    expect(mapsDatasetPath(WS, 'presence')).toBe(`${BASE}/presence`);
  });

  it('degrades to a workspace-less path before a workspace is known', () => {
    expect(mapsDatasetPath(null, 'earthquakes')).toBe('/maps/earthquakes');
  });
});

describe('mapsLibraryPath', () => {
  it('points at the maps library inside the workspace', () => {
    expect(mapsLibraryPath(WS)).toBe(BASE);
  });

  it('degrades to a workspace-less path before a workspace is known', () => {
    expect(mapsLibraryPath(null)).toBe('/maps');
  });
});
