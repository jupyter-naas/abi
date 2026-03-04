import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Middleware for route protection, legacy route redirects, and org-scoped routing.
 * 
 * Routing hierarchy:
 *   /account/*                        -> authed, global user settings
 *   /organizations                    -> authed, list orgs (if admin of multiple)
 *   /organizations/[orgId]/settings   -> authed, org settings
 *   /org/[orgSlug]/login              -> public, org-branded login
 *   /org/[orgSlug]/workspace          -> authed, workspace picker
 *   /org/[orgSlug]/workspace/[id]/... -> authed, rewrite to /workspace/[id]/...
 *   /auth/login                       -> public, default Nexus login
 *   /workspace/[id]/...               -> authed, existing workspace routes
 */

const DEFAULT_WORKSPACE = 'workspace-nexus';

// Legacy bare routes that should redirect to workspace-scoped routes
const legacyRoutes = [
  '/chat',
  '/search',
  '/lab',
  '/ontology',
  '/graph',
  '/apps',
  '/help',
  '/files',
  '/settings',
];

// Routes that are only for unauthenticated users
const authRoutes = [
  '/auth/login',
  '/auth/register',
  '/auth/forgot-password',
  '/login',        // Legacy alias
  '/register',     // Legacy alias
];

// Public routes (accessible to everyone)
const publicRoutes = [
  '/',
  '/terms',
  '/privacy',
];

// Regex to match /org/[slug]/workspace/[workspaceId]/...
const orgWorkspaceRegex = /^\/org\/([^/]+)\/workspace\/([^/]+)(\/.*)?$/;

// Regex to match /org/[slug]/login or /org/[slug]/register
const orgAuthRegex = /^\/org\/([^/]+)\/(login|register)(\/.*)?$/;

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // ============================================
  // Org-scoped routes
  // ============================================
  
  // /org/[orgSlug]/login and /org/[orgSlug]/register -> public, let through
  const orgAuthMatch = pathname.match(orgAuthRegex);
  if (orgAuthMatch) {
    return NextResponse.next();
  }
  
  // /org/[orgSlug]/workspace/[workspaceId]/... -> rewrite to /workspace/[workspaceId]/...
  // This avoids duplicating all workspace page files under the /org/ path.
  // The browser URL stays as /org/[orgSlug]/workspace/... but Next.js renders /workspace/...
  const orgWsMatch = pathname.match(orgWorkspaceRegex);
  if (orgWsMatch) {
    const [, orgSlug, workspaceId, rest] = orgWsMatch;
    const rewritePath = `/workspace/${workspaceId}${rest || ''}`;
    const rewriteUrl = new URL(rewritePath, request.url);
    rewriteUrl.search = request.nextUrl.search;
    return NextResponse.rewrite(rewriteUrl);
  }
  
  // /org/[orgSlug]/workspace (no workspaceId) -> workspace picker page, let through
  if (/^\/org\/[^/]+\/workspace\/?$/.test(pathname)) {
    return NextResponse.next();
  }
  
  // /org/[orgSlug] (bare org route) -> redirect to org workspace picker
  if (/^\/org\/[^/]+\/?$/.test(pathname)) {
    const orgSlug = pathname.split('/')[2];
    return NextResponse.redirect(new URL(`/org/${orgSlug}/workspace`, request.url));
  }
  
  // ============================================
  // Legacy route redirects
  // ============================================
  
  // Redirect legacy auth routes to /auth/* prefix
  if (pathname === '/login') {
    const newUrl = new URL('/auth/login', request.url);
    newUrl.search = request.nextUrl.search;
    return NextResponse.redirect(newUrl);
  }
  
  if (pathname === '/register') {
    const newUrl = new URL('/auth/register', request.url);
    newUrl.search = request.nextUrl.search;
    return NextResponse.redirect(newUrl);
  }
  
  // Redirect legacy bare routes to workspace-scoped routes
  // e.g., /chat -> /workspace/workspace-nexus/chat
  const isLegacyRoute = legacyRoutes.some(route => 
    pathname === route || pathname.startsWith(`${route}/`)
  );
  
  if (isLegacyRoute) {
    const newUrl = new URL(`/workspace/${DEFAULT_WORKSPACE}${pathname}`, request.url);
    newUrl.search = request.nextUrl.search;
    return NextResponse.redirect(newUrl);
  }
  
  // ============================================
  // Auth checks
  // ============================================
  
  // Check if user has auth token in cookies
  const hasAuthCookie = request.cookies.has('nexus-auth-flag');
  
  // Special handling for root path - always redirect based on auth
  if (pathname === '/') {
    if (hasAuthCookie) {
      // Authenticated: redirect to default workspace
      return NextResponse.redirect(new URL(`/workspace/${DEFAULT_WORKSPACE}/chat`, request.url));
    } else {
      // Not authenticated: redirect to login
      return NextResponse.redirect(new URL('/auth/login', request.url));
    }
  }
  
  // Check if current route is workspace-scoped (protected)
  const isWorkspaceRoute = pathname.startsWith('/workspace/');
  
  // Check if current route is organization-scoped (protected)
  const isOrganizationRoute = pathname.startsWith('/organizations/');
  
  // Check if current route is account-scoped (protected)
  const isAccountRoute = pathname.startsWith('/account/');
  
  // Check if current route is auth-only (login/register)
  const isAuthRoute = authRoutes.some(route => 
    pathname === route || pathname.startsWith(`${route}/`)
  );
  
  // For now, allow all routes in development
  // Authentication will be enforced client-side
  const isDev = process.env.NODE_ENV === 'development';
  
  if (isDev) {
    return NextResponse.next();
  }
  
  // In production, redirect unauthenticated users to login
  if ((isWorkspaceRoute || isOrganizationRoute || isAccountRoute) && !hasAuthCookie) {
    const loginUrl = new URL('/auth/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }
  
  // Redirect authenticated users away from auth pages
  if (isAuthRoute && hasAuthCookie) {
    return NextResponse.redirect(new URL(`/workspace/${DEFAULT_WORKSPACE}/chat`, request.url));
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
