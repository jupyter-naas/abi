import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  canInvalidateMapsLeaflet,
  captureMapsCamera,
  flyMapToUserLocation,
  mapsLocateZoomForAccuracy,
  mapsPinPopupHtml,
  observeMapsLeafletSize,
  restoreMapsCamera,
  safeInvalidateMapsLeafletSize,
} from './leaflet-map';

describe('mapsLocateZoomForAccuracy', () => {
  it('zooms in for a precise fix and eases out when accuracy is coarse', () => {
    expect(mapsLocateZoomForAccuracy(20)).toBe(17);
    expect(mapsLocateZoomForAccuracy(200)).toBe(15);
    expect(mapsLocateZoomForAccuracy(2000)).toBe(13);
    expect(mapsLocateZoomForAccuracy(undefined)).toBe(17);
  });
});

describe('flyMapToUserLocation', () => {
  it('flies to coordinates at the chosen zoom', () => {
    const flyTo = vi.fn();
    flyMapToUserLocation({ flyTo } as never, 48.85, 2.35, 30);
    expect(flyTo).toHaveBeenCalledWith([48.85, 2.35], 17, { duration: 0.65 });
  });
});

describe('maps camera restore', () => {
  it('flies back to the saved center and zoom', () => {
    const flyTo = vi.fn();
    const map = {
      getCenter: () => ({ lat: 20, lng: 0 }),
      getZoom: () => 3,
      flyTo,
    };
    const camera = captureMapsCamera(map as never);
    expect(camera).toEqual({ lat: 20, lng: 0, zoom: 3 });
    restoreMapsCamera(map as never, { lat: 20, lng: 0, zoom: 3 });
    expect(flyTo).toHaveBeenCalledWith([20, 0], 3, { duration: 0.55 });
  });
});

describe('mapsPinPopupHtml', () => {
  it('embeds a preview image that opens Street View', () => {
    const html = mapsPinPopupHtml({
      id: 'dc',
      lat: 38.9031704,
      lng: -77.0598347,
      label: 'Washington, DC',
    });
    expect(html).toContain('/api/maps/streetview?lat=38.9031704');
    expect(html).toContain('map_action=pano');
    expect(html).toContain('<img ');
    expect(html).not.toContain('Street View at this coordinate');
  });
});

describe('observeMapsLeafletSize', () => {
  const observers: ResizeObserverCallback[] = [];
  let observe: ReturnType<typeof vi.fn>;
  let disconnect: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    observers.length = 0;
    observe = vi.fn();
    disconnect = vi.fn();
    vi.stubGlobal('window', {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      setTimeout: (cb: () => void, ms?: number) =>
        globalThis.setTimeout(cb, ms) as unknown as number,
      clearTimeout: (id: number) => globalThis.clearTimeout(id),
    });
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(cb: ResizeObserverCallback) {
          observers.push(cb);
        }
        observe = observe;
        disconnect = disconnect;
        unobserve = vi.fn();
      },
    );
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('invalidates on observe, resize, and after panel transition', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const invalidateSize = vi.fn();
    const once = vi.fn();
    const container = {} as HTMLElement;
    const map = {
      getContainer: () => container,
      invalidateSize,
      once,
    };

    const stop = observeMapsLeafletSize(map as never);

    expect(observe).toHaveBeenCalledTimes(1);
    expect(invalidateSize).toHaveBeenCalledWith({ animate: false });

    invalidateSize.mockClear();
    observers[0]?.([], {} as ResizeObserver);
    expect(invalidateSize).toHaveBeenCalledWith({ animate: false });

    invalidateSize.mockClear();
    vi.advanceTimersByTime(320);
    expect(invalidateSize).toHaveBeenCalledWith({ animate: false });

    stop();
    expect(disconnect).toHaveBeenCalledTimes(1);
    expect(once).toHaveBeenCalledWith('unload', expect.any(Function));
  });

  it('does not invalidate after stop even if delayed callbacks fire', () => {
    const rafCallbacks: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      rafCallbacks.push(cb);
      return rafCallbacks.length;
    });
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });

    const invalidateSize = vi.fn();
    const map = {
      getContainer: () => ({ isConnected: true }) as HTMLElement,
      invalidateSize,
      once: vi.fn(),
      _mapPane: { isConnected: true },
    };

    const stop = observeMapsLeafletSize(map as never);
    expect(rafCallbacks).toHaveLength(1);

    stop();
    rafCallbacks[0]?.(0);
    vi.advanceTimersByTime(320);

    expect(invalidateSize).not.toHaveBeenCalled();
    expect(disconnect).toHaveBeenCalledTimes(1);
  });
});

describe('canInvalidateMapsLeaflet / safeInvalidateMapsLeafletSize', () => {
  it('rejects detached containers and missing map panes', () => {
    expect(canInvalidateMapsLeaflet(null)).toBe(false);
    expect(
      canInvalidateMapsLeaflet({
        getContainer: () => ({ isConnected: false }) as HTMLElement,
        invalidateSize: vi.fn(),
      } as never),
    ).toBe(false);
    expect(
      canInvalidateMapsLeaflet({
        getContainer: () => ({ isConnected: true }) as HTMLElement,
        invalidateSize: vi.fn(),
        _mapPane: null,
      } as never),
    ).toBe(false);
  });

  it('swallows invalidateSize errors from torn-down Leaflet maps', () => {
    const map = {
      getContainer: () => ({ isConnected: true }) as HTMLElement,
      invalidateSize: vi.fn(() => {
        throw new TypeError(
          "Cannot read properties of undefined (reading '_leaflet_pos')",
        );
      }),
      _mapPane: { isConnected: true },
    };
    expect(() => safeInvalidateMapsLeafletSize(map as never)).not.toThrow();
  });
});

describe('mapsCountryClusterLayersHtml', () => {
  it('renders one numbered badge per layer in its color', async () => {
    const { mapsCountryClusterLayersHtml, mapsCountryClusterBox } = await import('./leaflet-map');
    const html = mapsCountryClusterLayersHtml([
      { layerId: 'fm', title: 'Acme <b>', color: '#171c8f', count: 2 },
      { layerId: 'va', color: '#00a651', count: 120 },
    ]);
    expect(html).toContain('--maps-cluster-color:#171c8f');
    expect(html).toContain('--maps-cluster-color:#00a651');
    expect(html).toContain('>2<');
    expect(html).toContain('>120<');
    expect(html).toContain('font-size:9px');
    expect(html).toContain('title="2 Acme &lt;b&gt;"');
    expect(html).toContain('grid-template-columns:repeat(2,24px)');
    // One badge: its own size; several: a grid of at most 3 columns.
    expect(mapsCountryClusterBox(1)).toEqual({ width: 28, height: 28 });
    expect(mapsCountryClusterBox(2)).toEqual({ width: 50, height: 24 });
    expect(mapsCountryClusterBox(8)).toEqual({ width: 76, height: 76 });
  });

  it('never injects a non-hex color into the style attribute', async () => {
    const { mapsCountryClusterPinHtml } = await import('./leaflet-map');
    expect(mapsCountryClusterPinHtml('red;background:url(x)', 3)).toContain('--maps-cluster-color:#2563eb');
  });
});

describe('clusterCountLabel', () => {
  it('shows every count', async () => {
    const { clusterCountLabel } = await import('./leaflet-map');
    expect(clusterCountLabel(207)).toBe('207');
    expect(clusterCountLabel(999)).toBe('999');
    expect(clusterCountLabel(1234)).toBe('1.2k');
    expect(clusterCountLabel(15400)).toBe('15k');
  });
});
