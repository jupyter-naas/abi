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

describe('stored logos', () => {
  it('accepts object URLs of logos loaded with the member token', () => {
    expect(mapsPinImageUrl('blob:http://localhost:3000/1234')).toBe('blob:http://localhost:3000/1234');
    expect(resolveMapsPinImageUrl('blob:http://localhost:3000/1234')).toBe('blob:http://localhost:3000/1234');
    expect(mapsPinImageUrl('blob:javascript:alert(1)')).toBeUndefined();
  });
});
