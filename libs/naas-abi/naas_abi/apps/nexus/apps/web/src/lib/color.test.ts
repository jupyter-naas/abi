import { describe, expect, it } from 'vitest';
import { applyBrandColorVariables, brandColorVariables, hexToHslTriplet } from './color';

describe('hexToHslTriplet', () => {
  it('converts hex colours', () => {
    expect(hexToHslTriplet('#22c55e')).toBe('142 71% 45%');
    expect(hexToHslTriplet('ffffff')).toBe('0 0% 100%');
    expect(hexToHslTriplet('#000000')).toBe('0 0% 0%');
  });

  it('rejects anything else', () => {
    expect(hexToHslTriplet('red')).toBeNull();
    expect(hexToHslTriplet('#fff')).toBeNull();
    expect(hexToHslTriplet(null)).toBeNull();
  });
});

describe('brandColorVariables', () => {
  it('sets every colour token family', () => {
    expect(brandColorVariables('#22c55e', '#000000')).toEqual({
      '--primary': '142 71% 45%',
      '--accent': '0 0% 0%',
      '--ring': '142 71% 45%',
      '--workspace-primary': '#22c55e',
      '--workspace-accent': '#000000',
      '--workspace-primary-hsl': '142 71% 45%',
      '--workspace-accent-hsl': '0 0% 0%',
      '--color-primary': '#22c55e',
      '--color-primary-hover': 'color-mix(in srgb, #22c55e 80%, black)',
      '--color-primary-focus': 'color-mix(in srgb, #22c55e 30%, transparent)',
      '--color-primary-subtle': 'color-mix(in srgb, #22c55e 10%, transparent)',
    });
  });

  it('adds the # to bare hex colours', () => {
    expect(brandColorVariables('22c55e')['--color-primary']).toBe('#22c55e');
  });

  it('uses the primary as accent when there is none, and nothing for an invalid primary', () => {
    expect(brandColorVariables('#22c55e', null)['--accent']).toBe('142 71% 45%');
    expect(brandColorVariables('not-a-colour')).toEqual({});
  });
});

function fakeStyle(initial: Record<string, string>) {
  const values = new Map(Object.entries(initial));
  return {
    values,
    getPropertyValue: (name: string) => values.get(name) ?? '',
    setProperty: (name: string, value: string | null) => {
      values.set(name, value ?? '');
    },
    removeProperty: (name: string) => {
      const old = values.get(name) ?? '';
      values.delete(name);
      return old;
    },
  };
}

describe('applyBrandColorVariables', () => {
  it('replaces a workspace theme with the brand, then restores it', () => {
    const style = fakeStyle({ '--primary': '10 10% 10%', '--workspace-accent': '#111111' });
    const restore = applyBrandColorVariables(style, brandColorVariables('#0057B8', '#0B1F3A'));
    expect(style.values.get('--color-primary-subtle')).toBe(
      'color-mix(in srgb, #0057B8 10%, transparent)'
    );
    expect(style.values.get('--workspace-accent')).toBe('#0B1F3A');
    restore();
    expect(Object.fromEntries(style.values)).toEqual({
      '--primary': '10 10% 10%',
      '--workspace-accent': '#111111',
    });
  });

  it('without a brand, clears overrides so the platform defaults apply', () => {
    const style = fakeStyle({ '--primary': '10 10% 10%' });
    const restore = applyBrandColorVariables(style, {});
    expect(style.values.size).toBe(0);
    restore();
    expect(style.values.get('--primary')).toBe('10 10% 10%');
  });
});
