import { describe, expect, it } from 'vitest';

import { parseMapsVisibleCategories } from './maps-deployment';

describe('parseMapsVisibleCategories', () => {
  it('returns null when unset', () => {
    expect(parseMapsVisibleCategories(undefined)).toBeNull();
    expect(parseMapsVisibleCategories('')).toBeNull();
  });

  it('parses a single group', () => {
    expect(parseMapsVisibleCategories('organizations-facility')).toEqual([
      'organizations-facility',
    ]);
  });

  it('drops unknown groups', () => {
    expect(parseMapsVisibleCategories('environment,not-a-group')).toEqual(['environment']);
  });
});
