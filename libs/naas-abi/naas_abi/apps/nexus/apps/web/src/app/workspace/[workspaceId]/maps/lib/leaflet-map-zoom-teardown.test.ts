// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { guardMapsLeafletZoomTeardown } from './leaflet-map';

type ZoomInternals = {
  _animateZoom: (center: unknown, zoom: number, startAnim: boolean, noUpdate?: boolean) => void;
};

async function createZoomingMap(guard: boolean) {
  const L = await import('leaflet');
  const container = document.createElement('div');
  document.body.appendChild(container);
  const map = L.map(container, { zoomControl: false }).setView([20, 0], 2);
  if (guard) guardMapsLeafletZoomTeardown(map);
  // jsdom has no CSS 3D, so Leaflet never animates on its own: start the
  // animated zoom by hand, exactly as zoomIn() does in a browser.
  (map as unknown as ZoomInternals)._animateZoom(L.latLng(20, 0), 3, true);
  return { map, container };
}

describe('guardMapsLeafletZoomTeardown', () => {
  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = '';
  });

  it('reproduces the Leaflet 1.9 _leaflet_pos crash without the guard', async () => {
    vi.useFakeTimers();
    const { map } = await createZoomingMap(false);
    map.remove();
    expect(() => vi.advanceTimersByTime(300)).toThrow(/_leaflet_pos/);
  });

  it('ignores the late zoom transition end after map.remove()', async () => {
    vi.useFakeTimers();
    const { map } = await createZoomingMap(true);
    map.remove();
    expect(() => vi.advanceTimersByTime(300)).not.toThrow();
  });

  it('still finishes the zoom animation on a live map', async () => {
    vi.useFakeTimers();
    const { map } = await createZoomingMap(true);
    const zoomend = vi.fn();
    map.on('zoomend', zoomend);
    vi.advanceTimersByTime(300);
    expect(map.getZoom()).toBe(3);
    expect(zoomend).toHaveBeenCalledTimes(1);
    map.remove();
  });

  it('is idempotent', async () => {
    const L = await import('leaflet');
    const container = document.createElement('div');
    document.body.appendChild(container);
    const map = L.map(container).setView([0, 0], 2);
    guardMapsLeafletZoomTeardown(map);
    const wrapped = (map as unknown as { _onZoomTransitionEnd: unknown })._onZoomTransitionEnd;
    guardMapsLeafletZoomTeardown(map);
    expect((map as unknown as { _onZoomTransitionEnd: unknown })._onZoomTransitionEnd).toBe(wrapped);
    map.remove();
  });
});
