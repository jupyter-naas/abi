import { describe, expect, it } from 'vitest';

import { applyTenantShellBranding } from './tenant-shell';

function root(): HTMLElement {
  const props: Record<string, string> = {};
  return {
    dataset: {} as DOMStringMap,
    style: {
      setProperty(name: string, value: string) {
        props[name] = value;
      },
      getPropertyValue(name: string) {
        return props[name] ?? '';
      },
    },
  } as HTMLElement;
}

describe('applyTenantShellBranding', () => {
  it('brands the root and keeps a zero radius', () => {
    const el = root();
    applyTenantShellBranding(el, '0');
    expect(el.dataset.orgBranded).toBe('true');
    expect(el.style.getPropertyValue('--org-border-radius')).toBe('0px');
  });

  it('falls back to zero when the tenant left the radius empty', () => {
    const el = root();
    applyTenantShellBranding(el, undefined);
    expect(el.style.getPropertyValue('--org-border-radius')).toBe('0px');
  });
});
