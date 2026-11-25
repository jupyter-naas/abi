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

  it('shows the logo height, 48px when left out', () => {
    expect(row('logo', 'Logo height')).toEqual({
      key: 'logo_height',
      label: 'Logo height',
      value: { kind: 'text', text: '48px' },
    });
    const tall = siteIdentitySections({ ...SITE, logo_height: 96 }, ADDRESSES);
    const logo = tall.find((s) => s.id === 'logo');
    expect(logo?.rows.find((r) => r.key === 'logo_height')?.value).toEqual({ kind: 'text', text: '96px' });
  });

  it('shows the heading and the footer link next to the footer text, unset when left out', () => {
    expect(row('sign-in', 'Heading')?.value).toEqual({ kind: 'unset' });
    expect(row('sign-in', 'Footer link label')?.value).toEqual({ kind: 'unset' });
    expect(row('sign-in', 'Footer link')?.value).toEqual({ kind: 'unset' });

    const acme = siteIdentitySections(
      {
        ...SITE,
        login_heading: 'Acme Platform',
        login_footer_text: 'Acme Research operates this platform.',
        login_footer_link_label: 'Grant 123',
        login_footer_link_url: 'https://example.org/grant/123',
      },
      ADDRESSES
    ).find((s) => s.id === 'sign-in')!;
    const keys = acme.rows.map((r) => r.key);
    expect(keys.slice(keys.indexOf('login_heading'), keys.indexOf('login_footer_link_url') + 1)).toEqual([
      'login_heading',
      'login_footer_text',
      'login_footer_link_label',
      'login_footer_link_url',
    ]);
    expect(acme.rows.find((r) => r.key === 'login_heading')?.value).toEqual({ kind: 'text', text: 'Acme Platform' });
    expect(acme.rows.find((r) => r.key === 'login_footer_link_label')?.value).toEqual({
      kind: 'text',
      text: 'Grant 123',
    });
    expect(acme.rows.find((r) => r.key === 'login_footer_link_url')?.value).toEqual({
      kind: 'url',
      url: 'https://example.org/grant/123',
    });
  });

  it('lists the addresses the deployment decides, with no configuration key', () => {
    const addresses = siteIdentitySections(SITE, ADDRESSES).find((s) => s.id === 'addresses');
    expect(addresses?.rows).toEqual([
      { key: null, label: 'Web address', value: { kind: 'url', url: 'https://nexus.acme.example' } },
      { key: null, label: 'API address', value: { kind: 'url', url: 'https://api.acme.example' } },
    ]);
  });
});
