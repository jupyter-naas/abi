import { describe, expect, it } from 'vitest';

import { layerPaintColor, layerPinColor, sharedPinColor } from './maps-layer-colors';

describe('layerPinColor', () => {
  it('uses workspace hex colors when set', () => {
    expect(layerPinColor({ id: 'offices', color: '#ff00aa' })).toBe('#ff00aa');
  });

  it('uses built-in colors for known public feeds', () => {
    expect(layerPinColor({ id: 'wildfires' })).toBe('#dc2626');
  });

  it('falls back to a stable hash color for unknown ids', () => {
    expect(layerPinColor({ id: 'custom-feed-xyz' })).toMatch(/^#[0-9a-f]{6}$/i);
    expect(layerPinColor({ id: 'custom-feed-xyz' })).toBe(layerPinColor({ id: 'custom-feed-xyz' }));
  });
});

describe('layerPaintColor', () => {
  it('uses the layer hex when the catalog or Settings sent one', () => {
    expect(layerPaintColor({ id: 'custom-a', color: '#112233' }, [{ color: '#ffaa00' }, { color: '#ffaa00' }])).toBe(
      '#112233',
    );
  });

  it('uses a shared pin hex when the layer has no color', () => {
    expect(layerPaintColor({ id: 'custom-a' }, [{ color: '#ffaa00' }, { color: '#FFAA00' }])).toBe('#ffaa00');
    expect(sharedPinColor([{ color: '#16a34a' }, { color: '#aabbcc' }])).toBeUndefined();
  });

  it('falls back to the hash when pins do not share a color', () => {
    expect(layerPaintColor({ id: 'custom-a' }, [{ color: '#16a34a' }, { color: '#aabbcc' }])).toBe(
      layerPinColor({ id: 'custom-a' }),
    );
  });
});
