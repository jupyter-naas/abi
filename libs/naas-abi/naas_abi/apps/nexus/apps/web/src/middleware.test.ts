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

  it('allows magic-link confirmation when auth cookie is present', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(
      requestFor('/auth/magic-link?token=abc', { 'nexus-auth-flag': 'true' }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });

  it('marks the magic-link page as uncacheable', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(
      requestFor('/auth/magic-link?token=abc', { 'nexus-auth-flag': 'true' }),
    );
    expect(response.headers.get('cache-control')).toContain('no-store');
  });

  it('redirects other auth routes when auth cookie is present', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(
      requestFor('/auth/login', { 'nexus-auth-flag': 'true' }),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toMatch(/\/workspace\/.+\/chat/);
  });

  it('serves Platform Settings instead of redirecting it to a workspace', () => {
    process.env.NODE_ENV = 'production';

    for (const path of ['/settings', '/settings/users', '/settings/workspace_members']) {
      const response = middleware(requestFor(path, { 'nexus-auth-flag': 'true' }));
      expect(response.headers.get('location')).toBeNull();
    }
  });

  it('requires sign-in for Platform Settings', () => {
    process.env.NODE_ENV = 'production';

    const response = middleware(requestFor('/settings/users'));
    expect(response.headers.get('location')).toContain('/auth/login');
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
