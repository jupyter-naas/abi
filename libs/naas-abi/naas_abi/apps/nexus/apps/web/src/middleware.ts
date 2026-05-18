import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Route protection, legacy redirects, and org-scoped routing.
 *
 * Routing hierarchy:
 *   /account/*                        -> authed
 *   /organizations/[orgId]/settings   -> authed
 *   /org/[orgSlug]/login              -> public, org-branded login
 *   /org/[orgSlug]/workspace/[id]/... -> authed, rewritten to /workspace/[id]/...
 *   /auth/login                       -> public
 *   /workspace/[id]/...               -> authed
 *
 * Workspace redirect priority:
 *   1. nexus-last-workspace cookie
 *   2. DEFAULT_WORKSPACE env var (server-side, runtime — no NEXT_PUBLIC_ prefix)
 *   3. 'primary'
 */

const CONFIGURED_DEFAULT = process.env.DEFAULT_WORKSPACE || 'primary';

function resolveDefaultWorkspace(request: NextRequest): string {
  return request.cookies.get('nexus-last-workspace')?.value || CONFIGURED_DEFAULT;
}

const legacyRoutes = ['/chat', '/search', '/lab', '/code', '/ontology', '/graph', '/apps', '/marketplace', '/help', '/files', '/settings'];

const authRoutes = [
  '/auth/login',
  '/auth/magic-link',
  '/auth/register',
  '/auth/forgot-password',
  '/login',
  '/register',
];

const orgWorkspaceRegex = /^\/org\/([^/]+)\/workspace\/([^/]+)(\/.*)?$/;
const orgAuthRegex = /^\/org\/([^/]+)\/(login|register)(\/.*)?$/;

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.match(orgAuthRegex)) {
    return NextResponse.next();
  }

  // Rewrite /org/[slug]/workspace/[id]/... -> /workspace/[id]/...
  // Browser URL is preserved; Next.js renders the workspace pages without duplication.
  const orgWsMatch = pathname.match(orgWorkspaceRegex);
  if (orgWsMatch) {
    const [, , workspaceId, rest] = orgWsMatch;
    const rewriteUrl = new URL(`/workspace/${workspaceId}${rest || ''}`, request.url);
    rewriteUrl.search = request.nextUrl.search;
    return NextResponse.rewrite(rewriteUrl);
  }

  if (/^\/org\/[^/]+\/workspace\/?$/.test(pathname)) {
    return NextResponse.next();
  }

  if (/^\/org\/[^/]+\/?$/.test(pathname)) {
    const orgSlug = pathname.split('/')[2];
    return NextResponse.redirect(new URL(`/org/${orgSlug}/workspace`, request.url));
  }

  if (pathname === '/login' || pathname === '/register') {
    const newUrl = new URL(pathname === '/login' ? '/auth/login' : '/auth/register', request.url);
    newUrl.search = request.nextUrl.search;
    return NextResponse.redirect(newUrl);
  }

  const isLegacyRoute = legacyRoutes.some(r => pathname === r || pathname.startsWith(`${r}/`));
  if (isLegacyRoute) {
    const newUrl = new URL(`/workspace/${resolveDefaultWorkspace(request)}${pathname}`, request.url);
    newUrl.search = request.nextUrl.search;
    return NextResponse.redirect(newUrl);
  }

  const hasAuthCookie = request.cookies.has('nexus-auth-flag');

  if (pathname === '/') {
    return NextResponse.redirect(new URL(
      hasAuthCookie ? `/workspace/${resolveDefaultWorkspace(request)}/chat` : '/auth/login',
      request.url,
    ));
  }

  const isProtectedRoute = pathname.startsWith('/workspace/') || pathname.startsWith('/organizations/') || pathname.startsWith('/account/');
  const isAuthRoute = authRoutes.some(r => pathname === r || pathname.startsWith(`${r}/`));

  // In development auth is enforced client-side; still stamp the cookie so
  // production redirects work correctly after switching NODE_ENV.
  if (process.env.NODE_ENV === 'development') {
    const wsMatch = pathname.match(/^\/workspace\/([^/]+)/);
    if (wsMatch) {
      const res = NextResponse.next();
      res.cookies.set('nexus-last-workspace', wsMatch[1], { path: '/', maxAge: 60 * 60 * 24 * 30, sameSite: 'lax' });
      return res;
    }
    return NextResponse.next();
  }

  if (isProtectedRoute && !hasAuthCookie) {
    const loginUrl = new URL('/auth/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthRoute && hasAuthCookie) {
    return NextResponse.redirect(new URL(`/workspace/${resolveDefaultWorkspace(request)}/chat`, request.url));
  }

  const wsMatch = pathname.match(/^\/workspace\/([^/]+)/);
  if (wsMatch) {
    const res = NextResponse.next();
    res.cookies.set('nexus-last-workspace', wsMatch[1], { path: '/', maxAge: 60 * 60 * 24 * 30, sameSite: 'lax' });
    return res;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (public folder)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
