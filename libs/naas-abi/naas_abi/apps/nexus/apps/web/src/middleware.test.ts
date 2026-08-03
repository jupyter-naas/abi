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
});
