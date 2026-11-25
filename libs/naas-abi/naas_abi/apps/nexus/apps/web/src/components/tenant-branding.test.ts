// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot, type Root } from 'react-dom/client';
import { TenantFooter, TenantLogo, tenantFooterLink } from './tenant-branding';

// The tenant logo and footer the login and "No workspace yet" pages share.

let root: Root | undefined;
let host: HTMLDivElement | undefined;

function render(element: React.ReactElement): HTMLDivElement {
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(element));
  return host;
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = undefined;
  host = undefined;
});

const LINK = {
  login_footer_link_label: 'Grant 123',
  login_footer_link_url: 'https://example.org/grant/123',
};

describe('TenantFooter', () => {
  it('shows the footer text and, on its own line, the link opened in a new tab', () => {
    const el = render(
      React.createElement(TenantFooter, {
        tenant: { login_footer_text: 'Acme Research operates this platform.', ...LINK },
        color: '#000',
        className: 'mt-8',
      })
    );
    const footer = el.querySelector('p')!;
    expect(footer.className).toBe('text-center text-caption mt-8');
    expect([...footer.childNodes].map((n) => n.nodeName)).toEqual(['#text', 'BR', 'A']);
    const link = footer.querySelector('a')!;
    expect(link.getAttribute('href')).toBe('https://example.org/grant/123');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('shows the link alone, with no line break, when there is no footer text', () => {
    const footer = render(React.createElement(TenantFooter, { tenant: LINK, color: '#000' })).querySelector('p')!;
    expect([...footer.childNodes].map((n) => n.nodeName)).toEqual(['A']);
  });

  it('renders nothing when neither the text nor a link is set', () => {
    expect(render(React.createElement(TenantFooter, { tenant: {}, color: '#000' })).innerHTML).toBe('');
  });
});

describe('tenantFooterLink', () => {
  it('needs both the label and an http(s) URL', () => {
    expect(tenantFooterLink(LINK)).toEqual({ label: 'Grant 123', url: 'https://example.org/grant/123' });
    expect(tenantFooterLink({ login_footer_link_label: 'Grant 123' })).toBeNull();
    expect(tenantFooterLink({ login_footer_link_url: 'https://example.org' })).toBeNull();
    expect(tenantFooterLink({ login_footer_link_label: '  ', login_footer_link_url: 'https://example.org' })).toBeNull();
    expect(
      tenantFooterLink({ login_footer_link_label: 'x', login_footer_link_url: 'javascript:alert(1)' })
    ).toBeNull();
  });
});

describe('TenantLogo', () => {
  const base = { tab_title: 'Acme', logo_rectangle_url: null, logo_url: null, logo_emoji: null };

  it('is 48px high by default and logo_height pixels high when set', () => {
    let img = render(
      React.createElement(TenantLogo, {
        tenant: { ...base, logo_rectangle_url: 'https://example.org/wide.png' },
        radius: '0px',
        primaryColor: '#000',
      })
    ).querySelector('img')!;
    expect(img.style.height).toBe('48px');
    act(() => root!.unmount());
    host!.remove();

    img = render(
      React.createElement(TenantLogo, {
        tenant: { ...base, logo_rectangle_url: 'https://example.org/wide.png', logo_height: 96 },
        radius: '0px',
        primaryColor: '#000',
      })
    ).querySelector('img')!;
    expect(img.style.height).toBe('96px');
  });

  it('shows the emoji tile only where asked, at 48px whatever logo_height says', () => {
    const tenant = { ...base, logo_emoji: '🚀', logo_height: 96 };
    expect(
      render(React.createElement(TenantLogo, { tenant, radius: '0px', primaryColor: '#000' })).innerHTML
    ).toBe('');
    act(() => root!.unmount());
    host!.remove();

    const tile = render(
      React.createElement(TenantLogo, { tenant, radius: '0px', primaryColor: '#000', emojiFallback: true })
    ).querySelector('.mb-6 > div')!;
    expect(tile.textContent).toBe('🚀');
    expect(tile.className).toContain('h-12 w-12');
  });
});
