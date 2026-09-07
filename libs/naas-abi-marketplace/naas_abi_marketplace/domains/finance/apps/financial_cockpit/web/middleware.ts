import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

import { SESSION_COOKIE, verifySessionToken } from '@/lib/auth/jwt';
import { isAdminRole } from '@/lib/types';

const PUBLIC_PATHS = ['/login', '/api/auth/password'];

/**
 * Public static assets, matched by exact extension. This used to be a blanket
 * `pathname.includes('.')`, which made *any* path containing a dot public —
 * and since entity slugs are attacker-controlled, `/api/entities/a.b/data`
 * skipped this middleware entirely. Keep this list closed.
 */
const STATIC_ASSET_RE = /\.(?:png|jpe?g|gif|svg|webp|avif|ico|css|js|map|woff2?|ttf|txt|xml)$/;

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`))) {
    return true;
  }
  // API routes are never static assets — an extension there is always suspect.
  if (pathname.startsWith('/api/')) {
    return false;
  }
  if (pathname.startsWith('/_next') || STATIC_ASSET_RE.test(pathname)) {
    return true;
  }
  return false;
}

function isAdminPath(pathname: string): boolean {
  return pathname === '/admin' || pathname.startsWith('/admin/') || pathname.startsWith('/api/admin');
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  const session = await verifySessionToken(token);
  if (!session) {
    const response = NextResponse.redirect(new URL('/login', request.url));
    response.cookies.delete(SESSION_COOKIE);
    return response;
  }

  if (isAdminPath(pathname) && !isAdminRole(session.role)) {
    if (pathname.startsWith('/api/admin')) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    return NextResponse.redirect(new URL('/', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image).*)'],
};
