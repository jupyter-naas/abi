import { describe, expect, it } from 'vitest';

import { getFirmsWmsUrl, resolveFirmsMapKey } from './firms';

describe('resolveFirmsMapKey', () => {
  it('rejects empty and placeholder keys', () => {
    expect(resolveFirmsMapKey(undefined)).toBeNull();
    expect(resolveFirmsMapKey('')).toBeNull();
    expect(resolveFirmsMapKey('   ')).toBeNull();
    expect(resolveFirmsMapKey('MAP_KEY')).toBeNull();
    expect(resolveFirmsMapKey('map_key')).toBeNull();
    expect(resolveFirmsMapKey('YourMapKey')).toBeNull();
    expect(resolveFirmsMapKey('demo')).toBeNull();
  });

  it('rejects non-alphanumeric keys', () => {
    expect(resolveFirmsMapKey('../evil')).toBeNull();
    expect(resolveFirmsMapKey('abc def')).toBeNull();
    expect(resolveFirmsMapKey('key/with/slash')).toBeNull();
  });

  it('accepts a real-looking alphanumeric key', () => {
    expect(resolveFirmsMapKey('a1b2c3d4e5f6')).toBe('a1b2c3d4e5f6');
    expect(resolveFirmsMapKey('  Abc123  ')).toBe('Abc123');
  });
});

describe('getFirmsWmsUrl', () => {
  it('returns null without a valid key (never ships keyless FIRMS WMS)', () => {
    expect(getFirmsWmsUrl()).toBeNull();
    expect(getFirmsWmsUrl('MAP_KEY')).toBeNull();
  });

  it('builds the keyed FIRMS fires WMS base URL', () => {
    expect(getFirmsWmsUrl('a1b2c3d4e5f6')).toBe(
      'https://firms.modaps.eosdis.nasa.gov/mapserver/wms/fires/a1b2c3d4e5f6/',
    );
  });
});
