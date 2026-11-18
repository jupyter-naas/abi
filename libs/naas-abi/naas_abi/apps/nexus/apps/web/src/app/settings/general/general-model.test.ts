import { describe, expect, it } from 'vitest';
import { siteIdentitySections, siteName, type SiteIdentity } from './general-model';

const SITE: SiteIdentity = {
  name: 'Acme Portal',
  tab_title: 'Acme | Nexus',
  favicon_url: 'https://acme.example/favicon.ico',
  logo_url: '/logos/acme.png',
  logo_rectangle_url: null,
  logo_emoji: '',
  primary_color: '#003366',
  accent_color: '#0055AA',
  background_color: '#FFFFFF',
  login_card_max_width: '440px',
  login_card_padding: '2.5rem 3rem 3rem',
  login_card_color: '#FFFFFF',
  login_text_color: null,
  login_input_color: '#F4F4F4',
  login_border_radius: '0',
  show_terms_footer: false,
  show_powered_by: true,
};

const ADDRESSES = { webAddress: 'https://nexus.acme.example', apiAddress: 'https://api.acme.example' };

function row(sectionId: string, label: string) {
  const section = siteIdentitySections(SITE, ADDRESSES).find((s) => s.id === sectionId);
  return section?.rows.find((r) => r.label === label);
}

describe('siteName', () => {
  it('is the configured name, else the tab title', () => {
    expect(siteName(SITE)).toBe('Acme Portal');
    expect(siteName({ name: '  ', tab_title: 'Acme | Nexus' })).toBe('Acme | Nexus');
  });
});

describe('siteIdentitySections', () => {
  it('reads identity, default logo, sign-in page and addresses, in that order', () => {
    expect(siteIdentitySections(SITE, ADDRESSES).map((s) => s.id)).toEqual([
      'identity',
      'logo',
      'sign-in',
      'addresses',
    ]);
  });

  it('names each value by its key under tenant:', () => {
    expect(row('identity', 'Favicon')).toEqual({
      key: 'favicon_url',
      label: 'Favicon',
      value: { kind: 'image', url: 'https://acme.example/favicon.ico' },
    });
    expect(row('sign-in', 'Primary color')?.value).toEqual({ kind: 'color', color: '#003366' });
  });

  it('shows what is not configured as not set', () => {
    expect(row('logo', 'Wide logo')?.value).toEqual({ kind: 'unset' });
    expect(row('logo', 'Emoji')?.value).toEqual({ kind: 'unset' });
    expect(row('sign-in', 'Text color')?.value).toEqual({ kind: 'unset' });
  });

  it('gives a bare radius its unit and shows the footer switches', () => {
    expect(row('sign-in', 'Corner radius')?.value).toEqual({ kind: 'text', text: '0px' });
    expect(row('sign-in', '"Powered by" line')?.value).toEqual({ kind: 'flag', on: true });
  });

  it('lists the addresses the deployment decides, with no configuration key', () => {
    const addresses = siteIdentitySections(SITE, ADDRESSES).find((s) => s.id === 'addresses');
    expect(addresses?.rows).toEqual([
      { key: null, label: 'Web address', value: { kind: 'url', url: 'https://nexus.acme.example' } },
      { key: null, label: 'API address', value: { kind: 'url', url: 'https://api.acme.example' } },
    ]);
  });
});
