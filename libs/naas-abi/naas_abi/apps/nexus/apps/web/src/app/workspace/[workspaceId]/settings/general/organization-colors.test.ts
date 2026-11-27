import { describe, expect, it } from 'vitest';
import { organizationColors } from './organization-colors';

describe('organizationColors', () => {
  it('offers the organization primary and accent colors, named after it', () => {
    expect(organizationColors({ name: 'Acme', primary_color: '#0055FF', accent_color: '#ff8800' })).toEqual([
      { name: 'Acme primary', value: '#0055FF' },
      { name: 'Acme accent', value: '#ff8800' },
    ]);
  });

  it('leaves out an unset or invalid color, and one the same as the other', () => {
    expect(organizationColors({ primary_color: '#22c55e', accent_color: '#22C55E' })).toEqual([
      { name: 'Organization primary', value: '#22c55e' },
    ]);
    expect(organizationColors({ primary_color: 'blue' })).toEqual([]);
  });
});
