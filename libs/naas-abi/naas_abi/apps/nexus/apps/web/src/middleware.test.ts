import { afterEach, describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';

import { middleware } from './middleware';
import { LEGACY_WORKSPACE_SETTINGS_SLUGS } from './app/settings/lib/tables';
import { PLATFORM_SETTINGS_SECTIONS } from './app/settings/lib/redirects';

function requestFor(pathname: string, cookies: Record<string, string> = {}): NextRequest {
  const url = `https://nexus.example.com${pathname}`;
  const req = new NextRequest(url);
  for (const [name, value] of Object.entries(cookies)) {
    req.cookies.set(name, value);
  }
  return req;
}

describe('middleware auth redirects', () => {
  const originalNodeEnv = process.env.NODE_ENV;

  afterEach(() => {
    process.env.NODE_ENV = originalNodeEnv;
  });

  it('no longer treats the retired login pages as auth routes', () => {
    process.env.NODE_ENV = 'production';

    for (const path of ['/auth/register', '/auth/magic-link', '/auth/forgot-password']) {
      const response = middleware(requestFor(path, { 'nexus-auth-flag': 'true' }));
      expect(response.headers.get('location')).toBeNull();
    }
  });

  it('sends a visitor with no auth cookie from a protected route to the login', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(requestFor('/workspace/w/chat'));
    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toContain('/auth/login?redirect=');
  });

  it('redirects the login when auth cookie is present when auth cookie is present', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(
      requestFor('/auth/login', { 'nexus-auth-flag': 'true' }),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toMatch(/\/workspace\/.+\/chat/);
  });

  it('serves Platform Settings instead of redirecting it to a workspace', () => {
    process.env.NODE_ENV = 'production';

    for (const path of [
      '/settings',
      '/settings/tables',
      '/settings/tables/users',
      '/settings/tables/users/user-1',
      '/settings/system',
      '/settings/activity/events',
      '/settings/data/documents',
      '/settings/access/policies',
      '/settings/access/policies/builtin.owner',
      '/settings/users/usr_1',
    ]) {
      const response = middleware(requestFor(path, { 'nexus-auth-flag': 'true' }));
      expect(response.headers.get('location')).toBeNull();
    }
  });

  it('requires sign-in for Platform Settings', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(requestFor('/settings/tables/users'));
    expect(response.headers.get('location')).toContain('/auth/login');
  });

  it('redirects an old table page to Nexus tables', () => {
    process.env.NODE_ENV = 'production';

    const cookies = { 'nexus-auth-flag': 'true' };
    const users = middleware(requestFor('/settings/workspace_members', cookies));
    expect(users.status).toBe(307);
    expect(users.headers.get('location')).toBe(
      'https://nexus.example.com/settings/tables/workspace_members',
    );
    const userRow = middleware(requestFor('/settings/users/user-1', cookies));
    expect(userRow.headers.get('location')).toBe('https://nexus.example.com/settings/tables/users/user-1');
    // The Users page itself: no redirect.
    expect(middleware(requestFor('/settings/users', cookies)).headers.get('location')).toBeNull();
    const secrets = middleware(requestFor('/settings/secrets_table/s-1', cookies));
    expect(secrets.headers.get('location')).toBe(
      'https://nexus.example.com/settings/tables/secrets/s-1',
    );
  });

  it('redirects the old Roles & permissions pages to the Access page or the person they opened', () => {
    process.env.NODE_ENV = 'production';

    const cookies = { 'nexus-auth-flag': 'true' };
    const at = (path: string) => middleware(requestFor(path, cookies)).headers.get('location');
    expect(at('/settings/roles?section=policies')).toBe('https://nexus.example.com/settings/access/policies');
    expect(at('/settings/roles?section=people&person=usr_1')).toBe('https://nexus.example.com/settings/users/usr_1');
    expect(at('/organizations/org-1/settings/roles?section=groups')).toBe(
      'https://nexus.example.com/organizations/org-1/settings/groups',
    );
    expect(at('/workspace/ws-1/settings/permissions?section=policies&policy=pol_1')).toBe(
      'https://nexus.example.com/workspace/ws-1/settings/policies/pol_1',
    );
    expect(at('/org/acme/workspace/ws-1/settings/permissions?section=people')).toBe(
      'https://nexus.example.com/org/acme/workspace/ws-1/settings/members',
    );
  });

  it('redirects the old System and Events pages into Platform Settings', () => {
    process.env.NODE_ENV = 'production';

    const cookies = { 'nexus-auth-flag': 'true' };
    const traces = middleware(
      requestFor('/workspace/ws-1/admin/system?tab=traces&trace=abc', cookies),
    );
    expect(traces.headers.get('location')).toBe(
      'https://nexus.example.com/settings/activity/traces?trace=abc',
    );
    const access = middleware(requestFor('/org/acme/workspace/ws-1/admin/system?tab=access', cookies));
    expect(access.headers.get('location')).toBe('https://nexus.example.com/settings/access');
    const events = middleware(requestFor('/workspace/ws-1/admin/events', cookies));
    expect(events.headers.get('location')).toBe('https://nexus.example.com/settings/activity/events');
    const data = middleware(requestFor('/settings/system/data?service=cache', cookies));
    expect(data.headers.get('location')).toBe('https://nexus.example.com/settings/data/cache');
  });

  it('keeps redirecting legacy workspace settings links', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(
      requestFor('/settings/members', { 'nexus-auth-flag': 'true' }),
    );
    expect(response.headers.get('location')).toMatch(/\/workspace\/.+\/settings\/members$/);
  });

  it('redirects every legacy workspace settings link, even where a table shares the name', () => {
    process.env.NODE_ENV = 'production';

    // A slug Platform Settings now serves (General) is its page, not a legacy link.
    for (const slug of LEGACY_WORKSPACE_SETTINGS_SLUGS.filter((s) => !PLATFORM_SETTINGS_SECTIONS.includes(s))) {
      const response = middleware(
        requestFor(`/settings/${slug}`, { 'nexus-auth-flag': 'true' }),
      );
      expect(response.headers.get('location')).toMatch(
        new RegExp(`/workspace/.+/settings/${slug}$`),
      );
    }
  });

  it('serves Platform Settings › General at /settings/general', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(requestFor('/settings/general', { 'nexus-auth-flag': 'true' }));
    expect(response.headers.get('location')).toBeNull();
  });

  it('serves Platform Settings › Drives at /settings/drives, no longer a workspace link', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(requestFor('/settings/drives', { 'nexus-auth-flag': 'true' }));
    expect(response.headers.get('location')).toBeNull();
  });
});

describe('middleware: routes that fetch for a page', () => {
  const originalNodeEnv = process.env.NODE_ENV;

  afterEach(() => {
    process.env.NODE_ENV = originalNodeEnv;
  });

  it('keeps callers without a web pass out, in every mode', async () => {
    for (const mode of ['production', 'development']) {
      process.env.NODE_ENV = mode;
      for (const path of ['/api/image-data', '/api/link-preview', '/api/maps/place', '/api/maps/firms']) {
        // The page's own flag is no pass: page script sets it.
        const response = middleware(requestFor(path, { 'nexus-auth-flag': 'true' }));
        expect(response.status, `${mode} ${path}`).toBe(401);
        expect(response.headers.get('cache-control')).toBe('private, no-store');
      }
      const withPass = middleware(requestFor('/api/image-data', { 'nexus-web-pass': 'abi_gk_a_b' }));
      expect(withPass.status).toBe(200);
      expect(withPass.headers.get('x-middleware-next')).toBe('1');
    }
  });
});
