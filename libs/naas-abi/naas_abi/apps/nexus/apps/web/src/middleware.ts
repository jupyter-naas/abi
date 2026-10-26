import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { isPlatformSettingsPath, platformSettingsRedirect } from './app/settings/lib/redirects';

/**
 * Route protection, legacy redirects, and org-scoped routing.
 *
 * Routing hierarchy:
 *   /account/*                        -> authed
 *   /settings, /settings/{tables,system,roles}/... -> authed, Platform Settings
 *   /settings/<table>, /workspace/[id]/admin/{system,events} -> redirected there (old links)
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

const legacyRoutes = ['/home', '/maps', '/chat', '/search', '/lab', '/ontology', '/graph', '/apps', '/marketplace', '/help', '/files', '/settings'];

// Platform Settings owns /settings and its sections (Nexus tables, System, Roles &
// permissions, isPlatformSettingsPath); old table pages and System links redirect
// into them, and the legacy workspace settings links (/settings/members, ...) keep
// redirecting to the workspace.

const authRoutes = ['/auth/login', '/login'];

const orgWorkspaceRegex = /^\/org\/([^/]+)\/workspace\/([^/]+)(\/.*)?$/;
const orgAuthRegex = /^\/org\/([^/]+)\/login(\/.*)?$/;

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Before the org rewrite: /org/<slug>/workspace/<id>/admin/system moved too.
  const moved = platformSettingsRedirect(pathname, request.nextUrl.search);
  if (moved) {
    return NextResponse.redirect(new URL(moved, request.url));
  }

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

  if (pathname === '/login') {
    const newUrl = new URL('/auth/login', request.url);
    newUrl.search = request.nextUrl.search;
    return NextResponse.redirect(newUrl);
  }

  const isLegacyRoute =
    !isPlatformSettingsPath(pathname) &&
    legacyRoutes.some(r => pathname === r || pathname.startsWith(`${r}/`));
  if (isLegacyRoute) {
    const newUrl = new URL(`/workspace/${resolveDefaultWorkspace(request)}${pathname}`, request.url);
    newUrl.search = request.nextUrl.search;
    return NextResponse.redirect(newUrl);
  }

  const hasAuthCookie = request.cookies.has('nexus-auth-flag');

  // Custom Maps feeds are deployment-registered and may carry private data:
  // return 401 JSON (not a login redirect) when unauthenticated. Route handlers
  // still require a real session; this blocks anonymous curl.
  const isProtectedMapsApi = pathname.startsWith('/api/maps/custom/');
  if (isProtectedMapsApi && process.env.NODE_ENV !== 'development' && !hasAuthCookie) {
    return NextResponse.json(
      { error: 'Not authenticated', pins: [], count: 0 },
      { status: 401, headers: { 'Cache-Control': 'private, no-store' } },
    );
  }

  if (pathname === '/') {
    return NextResponse.redirect(new URL(
      hasAuthCookie ? `/workspace/${resolveDefaultWorkspace(request)}/chat` : '/auth/login',
      request.url,
    ));
  }

  const isProtectedRoute =
    pathname.startsWith('/workspace/') ||
    pathname.startsWith('/organizations/') ||
    pathname.startsWith('/account/') ||
    isPlatformSettingsPath(pathname) ||
    pathname === '/no-workspace' ||
    pathname.startsWith('/no-workspace/');
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
