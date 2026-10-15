import { describe, expect, it } from 'vitest';

import { layerPinColor } from './maps-layer-colors';

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
