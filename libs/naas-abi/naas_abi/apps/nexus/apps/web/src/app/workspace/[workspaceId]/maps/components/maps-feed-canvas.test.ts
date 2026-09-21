// @vitest-environment jsdom
import { act, createElement, StrictMode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MapsFeedCanvas } from './maps-feed-canvas';
import type { MapsFeedResult } from '../lib/maps-feed';
import type { MapsPinMarker } from '../lib/leaflet-map';

const pins: MapsPinMarker[] = Array.from({ length: 21 }, (_, index) => ({
  id: `office-${index}`,
  label: `Office ${index + 1}`,
  lat: 10 + index,
  lng: index,
  country: index < 2 ? 'Country A' : 'Country B',
  entityUri: `urn:office:${index}`,
  graphUri: 'urn:offices',
  sources: [{ title: 'Office listing', url: 'https://example.com/offices' }],
}));
let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  Object.defineProperty(SVGSVGElement.prototype, 'createSVGRect', { configurable: true, value: () => ({}) });
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    disconnect() {}
    unobserve() {}
  });
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

function renderFeed(fetchPins: (signal: AbortSignal) => Promise<MapsPinMarker[] | MapsFeedResult>, key = 'offices') {
  return createElement(StrictMode, null, createElement(MapsFeedCanvas, {
    key,
    title: 'Company offices',
    loadingLabel: 'Loading locations',
    readyMeta: count => `${count} locations`,
    fetchPins,
    inspectable: true,
    workspaceId: 'ws-test',
  }));
}

async function waitForUI(assertion: () => void) {
  let failure: unknown;
  for (let attempt = 0; attempt < 100; attempt++) {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
    try {
      assertion();
      return;
    } catch (error) {
      failure = error;
    }
  }
  throw failure;
}

async function waitForLocations(count: number) {
  await waitForUI(() => {
    expect(host.textContent).not.toContain('Map container is already initialized');
    expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(count);
  });
}

it('renders one real Leaflet map and all locations during Strict Mode remount', async () => {
  const fetchPins = vi.fn(async () => pins);
  await act(async () => root.render(renderFeed(fetchPins)));
  await waitForLocations(21);
  expect(host.querySelectorAll('.leaflet-map-pane')).toHaveLength(1);
  expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(21);
  expect(fetchPins).toHaveBeenCalledTimes(1);
  expect(host.querySelector('.maps-record-panel')).toBeNull();
  const pane = host.querySelector('.leaflet-map-pane');
  const tiles = Array.from(host.querySelectorAll<HTMLImageElement>('.leaflet-tile'));
  expect(tiles.length).toBeGreaterThan(0);
  expect(tiles.every(tile => new URL(tile.src).host === 'tile.openstreetmap.org')).toBe(true);
  expect(host.querySelector('.leaflet-control-attribution')?.textContent).toContain('OpenStreetMap');
  expect(host.querySelector('.leaflet-control-attribution')?.textContent).not.toContain('CARTO');

  const toggle = host.querySelector<HTMLButtonElement>('.maps-record-toggle')!;
  expect(toggle.getAttribute('aria-expanded')).toBe('false');
  await act(async () => toggle.click());
  expect(toggle.getAttribute('aria-expanded')).toBe('true');
  expect(host.querySelectorAll('.maps-record-list button')).toHaveLength(21);

  const country = host.querySelector('select')!;
  await act(async () => {
    country.value = 'Country A';
    country.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect(host.querySelectorAll('.maps-record-list button')).toHaveLength(2);
  expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(2);

  await act(async () => {
    host.querySelector<HTMLElement>('.leaflet-marker-icon')!.click();
  });
  expect(host.querySelector('.maps-record-panel h2')?.textContent).toBe('Office 1');
  const link = host.querySelector<HTMLAnchorElement>('.maps-record-kg')!;
  expect(new URL(link.href).searchParams.get('selected')).toBe('urn:office:0');
  expect(host.querySelector('.maps-record-sources')?.textContent).toContain('Office listing');
  const streetView = host.querySelector<HTMLAnchorElement>('.maps-record-streetview')!;
  expect(streetView.textContent).toContain('Street View');
  expect(streetView.target).toBe('_blank');
  expect(streetView.href).toBe('https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=10,0');
  expect(host.querySelector<HTMLAnchorElement>('.maps-record-images')?.href).toContain('tbm=isch');
  const preview = host.querySelector<HTMLImageElement>('.maps-record-photos img')!;
  expect(preview.src).toContain('/api/maps/streetview?lat=10&lng=0');
  expect(host.querySelector('.maps-record-photos__see')?.textContent).toBe('See photos');
  expect(host.querySelector('.maps-record-streetview-preview')).toBeNull();
  // The inspector is the only detail surface for graph markers.
  expect(host.querySelector('.leaflet-popup')).toBeNull();
  const leaflet = await import('leaflet');
  const flyTo = vi.spyOn(leaflet.Map.prototype, 'flyTo');
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Close location panel"]')!.click());
  expect(host.querySelector('.maps-record-panel')).toBeNull();
  expect(flyTo).toHaveBeenCalled();
  const restoredZoom = flyTo.mock.calls.at(-1)?.[1];
  expect(Number(restoredZoom)).toBeLessThan(14);
  flyTo.mockRestore();
  expect(host.querySelector('.leaflet-map-pane')).toBe(pane);
  expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(2);
  await act(async () => host.querySelector<HTMLElement>('.leaflet-marker-icon')!.click());
  expect(host.querySelector('.maps-record-panel h2')?.textContent).toBe('Office 1');
});

it('disposes the previous map and ignores a stale feed after switching datasets', async () => {
  let finishOld!: (value: MapsPinMarker[]) => void;
  let oldSignal: AbortSignal | undefined;
  const oldFeed = vi.fn((signal: AbortSignal) => {
    oldSignal = signal;
    return new Promise<MapsPinMarker[]>(resolve => { finishOld = resolve; });
  });
  await act(async () => root.render(renderFeed(oldFeed, 'old')));
  await waitForUI(() => expect(oldFeed).toHaveBeenCalledTimes(1));
  const oldContainer = host.querySelector('.leaflet-container')!;
  const currentFeed = vi.fn(async () => pins);
  await act(async () => root.render(renderFeed(currentFeed, 'current')));
  await waitForLocations(21);
  expect(oldSignal?.aborted).toBe(true);
  expect(oldContainer.querySelector('.leaflet-map-pane')).toBeNull();
  await act(async () => finishOld([{ ...pins[0], label: 'Stale office' }]));
  expect(host.textContent).not.toContain('Stale office');
  expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(21);
});

it('accepts a feed result object and shows attribution and freshness', async () => {
  const fetchPins = vi.fn(async () => ({
    pins,
    source: 'aisstream',
    attribution: 'AISStream',
    observedAt: new Date().toISOString(),
    coverage: 'viewport',
  }));
  await act(async () => root.render(renderFeed(fetchPins)));
  await waitForLocations(21);
  expect(host.textContent).toContain('AISStream');
  expect(host.textContent).toContain('viewport');
  expect(host.textContent).toMatch(/just now|s ago/);
});


const addressPins: MapsPinMarker[] = [
  {id:'paris-one',entityUri:'urn:address:one',graphUri:'urn:offices',label:'Paris',country:'France',lat:48.86,lng:2.36,detail:'5 Rue Charlot\nRegistered establishment'},
  {id:'paris-two',entityUri:'urn:address:two',graphUri:'urn:offices',label:'Paris (legal head office)',country:'France',lat:48.87,lng:2.31,detail:'162 Boulevard Haussmann\nRegistered head office'},
  {id:'new-york',entityUri:'urn:address:ny',graphUri:'urn:offices',label:'New York',country:'United States',lat:40.74,lng:-73.99},
];
const cityPins: MapsPinMarker[] = [
  {id:'city-paris',entityUri:'urn:city:paris',graphUri:'urn:offices',label:'Paris',country:'France',lat:48.85,lng:2.35,memberIds:['paris-one','paris-two']},
  {id:'city-new-york',entityUri:'urn:city:ny',graphUri:'urn:offices',label:'New York',country:'United States',lat:40.71,lng:-74,memberIds:['new-york']},
];
const borders = { type:'FeatureCollection', features: [
  {type:'Feature',properties:{NAME_EN:'France'},geometry:{type:'Polygon',coordinates:[[[0,40],[0,50],[8,50],[8,40],[0,40]]]}},
  {type:'Feature',properties:{NAME_EN:'United States of America'},geometry:{type:'Polygon',coordinates:[[[-125,25],[-125,50],[-65,50],[-65,25],[-125,25]]]}},
  {type:'Feature',properties:{NAME_EN:'Germany'},geometry:{type:'Polygon',coordinates:[[[9,47],[9,55],[15,55],[15,47],[9,47]]]}},
] };

function coverageButton() {
  return Array.from(host.querySelectorAll<HTMLButtonElement>('.maps-view-switch button')).find(button=>button.textContent==='City coverage')!;
}

it('switches to city coverage, shades only represented countries and drills from country to city to address', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true,json:async()=>borders}));
  await act(async () => root.render(renderFeed(async()=>({pins:addressPins,coveragePins:cityPins}))));
  await waitForLocations(3);
  const pane=host.querySelector('.leaflet-map-pane');
  await act(async()=>coverageButton().click());
  await waitForLocations(2);
  await waitForUI(()=>expect(host.querySelectorAll('.maps-coverage-country')).toHaveLength(2));
  expect(host.querySelector('.maps-canvas__toolbar-meta')?.textContent).toBe('2 cities · 2 countries');
  expect(host.querySelector('.leaflet-control-attribution')?.textContent).toContain('Natural Earth');
  expect(host.querySelector('.leaflet-map-pane')).toBe(pane);
  await act(async()=>host.querySelector('[aria-label="France · 1 city"]')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));
  expect(host.querySelectorAll('.maps-record-list button')).toHaveLength(1);
  expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(1);
  await act(async()=>host.querySelector<HTMLButtonElement>('.maps-record-list button')!.click());
  expect(host.querySelector('.maps-record-panel h2')?.textContent).toBe('Paris');
  expect(host.querySelectorAll('.maps-coverage-addresses button')).toHaveLength(2);
  expect(new URL(host.querySelector<HTMLAnchorElement>('.maps-record-kg')!.href).searchParams.get('selected')).toBe('urn:city:paris');
  await act(async()=>host.querySelectorAll<HTMLButtonElement>('.maps-coverage-addresses button')[1].click());
  expect(host.querySelector('.maps-view-switch button')?.getAttribute('aria-pressed')).toBe('true');
  expect(host.querySelector('.maps-record-panel')?.textContent).toContain('162 Boulevard Haussmann');
  expect(new URL(host.querySelector<HTMLAnchorElement>('.maps-record-kg')!.href).searchParams.get('selected')).toBe('urn:address:two');
  expect(host.querySelectorAll('.maps-coverage-country')).toHaveLength(0);
  expect(host.querySelector('.leaflet-control-attribution')?.textContent).not.toContain('Natural Earth');
  await act(async()=>coverageButton().click());
  await waitForUI(()=>expect(host.querySelectorAll('.maps-coverage-country')).toHaveLength(2));
  await waitForUI(()=>expect(host.querySelector('[aria-label="Clear map filters"]')).toBeTruthy());
  await act(async()=>host.querySelector<HTMLButtonElement>('[aria-label="Clear map filters"]')!.click());
  expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(2);
  expect(host.querySelector('.leaflet-map-pane')).toBe(pane);
});

it('keeps city data usable when the country boundary provider fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Offline')));
  await act(async()=>root.render(renderFeed(async()=>({pins:addressPins,coveragePins:cityPins}))));
  await waitForLocations(3);
  await act(async()=>coverageButton().click());
  await waitForUI(()=>expect(host.textContent).toContain('Country shading unavailable'));
  expect(host.querySelectorAll('.leaflet-marker-icon')).toHaveLength(2);
  expect(host.textContent).not.toContain('Feed unavailable');
});
