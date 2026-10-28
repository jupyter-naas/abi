import { describe, expect, it } from 'vitest';

import { mapsLayerPinHtml } from './maps-layer-pin-html';

describe('mapsLayerPinHtml', () => {
  it('renders a colored badge with an inline icon', () => {
    const html = mapsLayerPinHtml('Flame', '#dc2626');
    expect(html).toContain('maps-layer-marker');
    expect(html).toContain('#dc2626');
    expect(html).toContain('<svg');
  });
});
