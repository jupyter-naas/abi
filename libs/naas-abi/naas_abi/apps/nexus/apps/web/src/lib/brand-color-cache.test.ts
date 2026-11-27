// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { BRAND_BOOT_STYLE_ID, BRAND_COLOR_BOOT, brandScopeOf, rememberBrandColors } from './brand-color-cache';

const boot = () => new Function(BRAND_COLOR_BOOT)();
const sheet = () => document.getElementById(BRAND_BOOT_STYLE_ID)?.textContent ?? null;

beforeEach(() => {
  localStorage.clear();
  document.getElementById(BRAND_BOOT_STYLE_ID)?.remove();
});

afterEach(() => {
  document.getElementById(BRAND_BOOT_STYLE_ID)?.remove();
  window.history.replaceState(null, '', '/');
});

describe('the brand colors kept for a hard refresh', () => {
  it('names a page by the workspace or the organization of its path, its Settings apart', () => {
    expect(brandScopeOf('/workspace/ws-1/home')).toBe('workspace:ws-1');
    expect(brandScopeOf('/workspace/ws-1/settings/general')).toBe('workspace:ws-1/settings');
    expect(brandScopeOf('/organizations/org-1/settings/branding')).toBe('organization:org-1/settings');
    expect(brandScopeOf('/account/profile')).toBeNull();
    expect(brandScopeOf('/settings/general')).toBeNull();
  });

  it('paints the colors last seen on a page before the app runs, in a sheet the app then drops', () => {
    rememberBrandColors('/workspace/ws-1/home', { '--workspace-accent': '#3b82f6', '--primary': '217 91% 60%' });
    window.history.replaceState(null, '', '/workspace/ws-1/chat');

    boot();
    expect(sheet()).toBe(':root{--workspace-accent:#3b82f6;--primary:217 91% 60%;}');
    // The app applies its own colors: the sheet goes.
    rememberBrandColors('/workspace/ws-1/chat', { '--workspace-accent': '#3b82f6' });
    expect(sheet()).toBeNull();
  });

  it('adds what both shells of a Settings page apply', () => {
    rememberBrandColors('/workspace/ws-1/settings/general', { '--color-primary': '#3b82f6' });
    rememberBrandColors('/workspace/ws-1/settings/general', { '--workspace-accent': '#3b82f6' });
    window.history.replaceState(null, '', '/workspace/ws-1/settings/users');
    boot();
    expect(sheet()).toBe(':root{--color-primary:#3b82f6;--workspace-accent:#3b82f6;}');
  });

  it('paints nothing on another workspace, another kind of page or a page of no scope', () => {
    rememberBrandColors('/workspace/ws-1/home', { '--workspace-accent': '#3b82f6' });
    for (const path of ['/workspace/ws-2/home', '/workspace/ws-1/settings/general', '/organizations/org-1/settings', '/account/profile']) {
      window.history.replaceState(null, '', path);
      boot();
      expect(sheet()).toBeNull();
    }
  });

  it('paints nothing during a view (View as): the viewer keeps nothing of the real browser', () => {
    rememberBrandColors('/workspace/ws-1/home', { '--workspace-accent': '#3b82f6' });
    window.history.replaceState(null, '', '/workspace/ws-1/home');
    document.cookie = 'nexus-view-as=1; path=/';
    try {
      boot();
      expect(sheet()).toBeNull();
    } finally {
      document.cookie = 'nexus-view-as=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    }
  });

  it('forgets a page back to the platform colors, and never puts back anything but colors', () => {
    rememberBrandColors('/organizations/org-1/settings', { '--color-primary': '#0057B8' });
    rememberBrandColors('/organizations/org-1/settings', {});
    window.history.replaceState(null, '', '/organizations/org-1/settings/general');
    boot();
    expect(sheet()).toBeNull();

    localStorage.setItem(
      'nexus-brand-colors',
      JSON.stringify({ 'organization:org-1/settings': { color: 'red', '--x': 'url(evil)', '--y': '#fff}body{x:1' } })
    );
    boot();
    expect(sheet()).toBeNull();
  });
});
