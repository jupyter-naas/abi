// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));

import PlatformGeneralPage from './general';

let site: Record<string, unknown>;
let mounted: Mounted | null = null;

beforeEach(() => {
  site = {
    name: 'Bob',
    tab_title: 'Bob platform',
    primary_color: '#22c55e',
    accent_color: '#16a34a',
    background_color: '#000000',
    login_card_max_width: '420px',
    login_card_padding: '32px',
    login_card_color: '#111111',
    login_input_color: '#222222',
    login_border_radius: '0',
    show_terms_footer: true,
    show_powered_by: false,
  };
  vi.stubGlobal('fetch', vi.fn(async () => Response.json(site)));
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.unstubAllGlobals();
});

async function open() {
  mounted = await mount(PlatformGeneralPage, {});
  for (let i = 0; i < 10 && !mounted.host.querySelector('[data-platform-identity]'); i += 1) await mounted.flush();
  return mounted;
}

describe('Platform › General is laid out as Organization › General', () => {
  it('heads the page with the platform: its logo or initial, name, address and what it is', async () => {
    const m = await open();
    const head = m.host.querySelector('[data-platform-identity]')!;
    expect(head.querySelector('h3')?.textContent).toBe('Bob');
    expect(head.querySelector('[data-platform-initial]')?.textContent).toBe('B');
    expect(head.textContent).toContain('Shared by every organization');
    expect(head.textContent).toContain('tenant:');
  });

  it('shows the square logo when the platform has one', async () => {
    site = { ...site, logo_url: 'https://cdn.example.test/logo.png' };
    const m = await open();
    expect(m.host.querySelector('[data-platform-identity] img')?.getAttribute('src')).toBe(
      'https://cdn.example.test/logo.png'
    );
  });

  it('titles its sections as the other settings pages', async () => {
    const m = await open();
    expect([...m.host.querySelectorAll('section h3')].map((h) => h.textContent)).toEqual([
      'Site identity',
      'Default logo',
      'Sign-in page',
      'Addresses',
    ]);
    expect(m.host.querySelector('.org-settings-card-heading-title')).toBeNull();
  });
});
