import { afterEach, describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';

import { middleware } from './middleware';
import { LEGACY_WORKSPACE_SETTINGS_SLUGS } from './app/settings/lib/tables';

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
      '/settings/system/events',
      '/settings/roles',
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
    const users = middleware(requestFor('/settings/users', cookies));
    expect(users.status).toBe(307);
    expect(users.headers.get('location')).toBe('https://nexus.example.com/settings/tables/users');
    const secrets = middleware(requestFor('/settings/secrets_table/s-1', cookies));
    expect(secrets.headers.get('location')).toBe(
      'https://nexus.example.com/settings/tables/secrets/s-1',
    );
  });

  it('redirects the old System and Events pages into Platform Settings', () => {
    process.env.NODE_ENV = 'production';

    const cookies = { 'nexus-auth-flag': 'true' };
    const traces = middleware(
      requestFor('/workspace/ws-1/admin/system?tab=traces&trace=abc', cookies),
    );
    expect(traces.headers.get('location')).toBe(
      'https://nexus.example.com/settings/system/traces?trace=abc',
    );
    const access = middleware(requestFor('/org/acme/workspace/ws-1/admin/system?tab=access', cookies));
    expect(access.headers.get('location')).toBe('https://nexus.example.com/settings/roles');
    const events = middleware(requestFor('/workspace/ws-1/admin/events', cookies));
    expect(events.headers.get('location')).toBe('https://nexus.example.com/settings/system/events');
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

    for (const slug of LEGACY_WORKSPACE_SETTINGS_SLUGS) {
      const response = middleware(
        requestFor(`/settings/${slug}`, { 'nexus-auth-flag': 'true' }),
      );
      expect(response.headers.get('location')).toMatch(
        new RegExp(`/workspace/.+/settings/${slug}$`),
      );
    }
  });
});
