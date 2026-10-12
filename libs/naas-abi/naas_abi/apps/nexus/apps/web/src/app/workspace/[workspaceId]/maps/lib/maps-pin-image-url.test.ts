import { describe, expect, it } from 'vitest';

import { mapsPinImageUrl, resolveMapsPinImageUrl } from './maps-pin-image-url';

describe('mapsPinImageUrl', () => {
  it('accepts HTTPS and /api paths', () => {
    expect(mapsPinImageUrl('https://example.com/a.png')).toBe('https://example.com/a.png');
    expect(mapsPinImageUrl('/api/organizations/logos/Valeo/Valeo.jpg')).toBe(
      '/api/organizations/logos/Valeo/Valeo.jpg',
    );
  });
});

describe('resolveMapsPinImageUrl', () => {
  it('leaves HTTPS unchanged', () => {
    expect(resolveMapsPinImageUrl('https://example.com/a.png')).toBe('https://example.com/a.png');
  });
});
