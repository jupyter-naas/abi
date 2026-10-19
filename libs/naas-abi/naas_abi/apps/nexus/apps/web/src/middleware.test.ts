import { afterEach, describe, expect, it } from 'vitest';
import { NextRequest } from 'next/server';

import { middleware } from './middleware';

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
});
