import { describe, expect, it } from 'vitest';

import {
  datasetsCatalogPath,
  datasetsTablePath,
  parseDatasetsRoute,
} from './datasets-route';

const WS = 'ws-1';
const BASE = `/workspace/${WS}/datasets`;

describe('parseDatasetsRoute', () => {
  it('shows the catalog on the bare datasets route', () => {
    expect(parseDatasetsRoute(BASE)).toEqual({
      isDatasetsRoute: true,
      isTable: false,
      namespace: null,
      name: null,
    });
  });

  it('treats a namespace-only path as catalog, not a table', () => {
    expect(parseDatasetsRoute(`${BASE}/clockify`)).toEqual({
      isDatasetsRoute: true,
      isTable: false,
      namespace: 'clockify',
      name: null,
    });
  });

  it('opens a table on /datasets/{namespace}/{name}', () => {
    expect(parseDatasetsRoute(`${BASE}/clockify/hours`)).toEqual({
      isDatasetsRoute: true,
      isTable: true,
      namespace: 'clockify',
      name: 'hours',
    });
  });

  it('stops at a query string or fragment', () => {
    expect(parseDatasetsRoute(`${BASE}/clockify/hours?limit=10`).isTable).toBe(true);
    expect(parseDatasetsRoute(`${BASE}/clockify/hours#rows`).name).toBe('hours');
  });

  it('does not claim routes that merely contain the word datasets', () => {
    expect(parseDatasetsRoute(`/workspace/${WS}/chat`).isDatasetsRoute).toBe(false);
    expect(parseDatasetsRoute(`/workspace/${WS}/datasetshare`).isDatasetsRoute).toBe(false);
  });

  it('treats a missing pathname as no route at all', () => {
    expect(parseDatasetsRoute(null).isDatasetsRoute).toBe(false);
    expect(parseDatasetsRoute(undefined).isDatasetsRoute).toBe(false);
  });
});

describe('datasets paths', () => {
  it('points at catalog and table inside the workspace', () => {
    expect(datasetsCatalogPath(WS)).toBe(BASE);
    expect(datasetsTablePath(WS, 'clockify', 'hours')).toBe(`${BASE}/clockify/hours`);
  });

  it('degrades to a workspace-less path before a workspace is known', () => {
    expect(datasetsCatalogPath(null)).toBe('/datasets');
    expect(datasetsTablePath(null, 'github', 'commits')).toBe('/datasets/github/commits');
  });
});
