// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));
const authFetch = vi.hoisted(() => vi.fn());
vi.mock('@/stores/auth', async (original) => ({ ...(await original<object>()), authFetch }));

import { useOrganizationStore, type Organization } from '@/stores/organization';
import { OrgBrandingSettings } from './org-branding-settings';

const ACME = { id: 'acme', name: 'Acme', slug: 'acme', ownerId: 'olivia', logoEmoji: '🦊' } as Organization;

let mounted: Mounted | null = null;

beforeEach(() => {
  authFetch.mockReset();
  authFetch.mockResolvedValue(Response.json({ logo_rectangle_url: '/uploads/acme-wide.png' }));
  useOrganizationStore.setState({ organizations: [ACME], fetchOrganizations: vi.fn(async () => undefined) } as never);
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function open() {
  mounted = await mount(OrgBrandingSettings, { orgId: 'acme', orgDisplayName: 'Acme' });
  await mounted.flush();
  return mounted;
}

describe('Organization › Branding', () => {
  it('titles its sections as the other settings pages, the two logos apart', async () => {
    const m = await open();
    expect([...m.host.querySelectorAll('section h3')].map((h) => h.textContent)).toEqual([
      'Square logo',
      'Wide logo',
      'Brand colors',
      'Login page background',
      'Login card and inputs',
      'Default workspace theme',
      'Login page footer',
    ]);
    expect(m.host.querySelector('.uppercase')).toBeNull();
    // Without logos: the square block shows the emoji, the wide one says what stands in.
    expect(m.host.querySelector('[data-logo-preview="square"] [data-logo-fallback]')?.textContent).toBe('🦊');
    expect(m.host.querySelector('[data-logo-preview="rectangle"]')?.textContent).toContain('No wide logo');
  });

  it('uploads each logo from its own block', async () => {
    const m = await open();
    const input = m.host.querySelectorAll<HTMLInputElement>('input[type="file"]')[1];
    const file = new File(['png'], 'wide.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    const { act } = await import('react');
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    await m.flush();
    expect(authFetch).toHaveBeenCalledWith('/api/organizations/acme/upload-logo-rectangle', expect.objectContaining({ method: 'POST' }));
    expect(m.host.querySelector<HTMLImageElement>('[data-logo-preview="rectangle"] img')?.getAttribute('src')).toBe(
      'https://api.example.test/uploads/acme-wide.png'
    );
  });
});
