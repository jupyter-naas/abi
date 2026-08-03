import { cookies } from 'next/headers';

import type { PageId, SessionPayload, UserConfig } from '@/lib/types';
import { isAdminRole, normalizePageId } from '@/lib/types';
import { listProtectedUsers, getUserById } from '@/lib/server/financeUsers';
import {
  SESSION_COOKIE,
  SESSION_MAX_AGE_SECONDS,
  createSessionToken,
  verifySessionToken,
} from '@/lib/auth/jwt';

export { SESSION_COOKIE, createSessionToken, verifySessionToken };

export function buildSessionPayload(user: UserConfig): SessionPayload {
  return {
    userId: user.user_id,
    displayName: user.name,
    role: user.role,
    allowedEntities: user.allowed_entities ?? [],
    allowedPages: (user.allowed_pages ?? [])
      .map((pageId) => normalizePageId(pageId))
      .filter((pageId): pageId is PageId => pageId !== null),
  };
}

/**
 * Rebuild the session from the *current* user record instead of trusting the
 * permissions frozen into the 7-day JWT. Without this, editing or deleting a
 * user in /admin/users had no effect until their cookie expired — a removed
 * user kept full access for up to a week.
 *
 * Returns null when the user no longer exists, which invalidates the cookie.
 * Note the middleware still only verifies the JWT signature (it cannot reach
 * the datastore), so a revoked user is stopped here, at the page/route gate,
 * rather than being redirected to /login.
 */
async function resolveLiveSession(
  session: SessionPayload,
): Promise<SessionPayload | null> {
  // The shared root password yields a synthetic session with no user record;
  // the ROOT_PASSWORD secret is its authority, so keep the token's claims.
  if (session.userId.startsWith('pwd:')) {
    return session;
  }

  const user = await getUserById(session.userId);
  if (!user) {
    return null;
  }
  return buildSessionPayload(user);
}

export async function getSession(): Promise<SessionPayload | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  if (!token) {
    return null;
  }
  const session = await verifySessionToken(token);
  if (!session) {
    return null;
  }
  return resolveLiveSession(session);
}

export async function setSessionCookie(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
}

export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE);
}

export async function requireSession(): Promise<SessionPayload> {
  const session = await getSession();
  if (!session) {
    throw new Error('UNAUTHORIZED');
  }
  return session;
}

/**
 * Admin gate for Server Components / pages. Throws UNAUTHORIZED / FORBIDDEN —
 * catch at the page level with `.catch(() => notFound())`.
 */
export async function requireAdmin(): Promise<SessionPayload> {
  const session = await requireSession();
  if (!(await isAdminSession(session))) {
    throw new Error('FORBIDDEN');
  }
  return session;
}

export async function requireThemePageAccess(): Promise<SessionPayload> {
  const session = await requireSession();
  const { canAccessThemePage } = await import('@/lib/config/loadConfig');
  if (!canAccessThemePage(session)) {
    throw new Error('FORBIDDEN');
  }
  return session;
}

export async function requireEntityPageAccess(
  entityId: string,
  pageId: SessionPayload['allowedPages'][number],
): Promise<SessionPayload> {
  const session = await requireSession();
  const { canAccess } = await import('@/lib/config/loadConfig');
  if (!canAccess(session, entityId, pageId)) {
    throw new Error('FORBIDDEN');
  }
  return session;
}

/**
 * Owner and admin both count as admin-level. Sessions from `getSession` are
 * already rebuilt from the live user record (see resolveLiveSession), so the
 * role here is current; the config lookup still takes precedence so an owner
 * declared in config.yaml is admin-level even for a synthetic `pwd:*` session.
 */
export async function isAdminSession(session: SessionPayload): Promise<boolean> {
  const protectedRole = listProtectedUsers().find(
    (u) => u.user_id === session.userId,
  )?.role;
  return isAdminRole(protectedRole ?? session.role);
}

export async function getUserFromSession(session: SessionPayload): Promise<UserConfig> {
  const user = await getUserById(session.userId);
  if (user) {
    return user;
  }
  // Password sign-in yields a synthetic admin session (`pwd:admin`) with no
  // matching config user. Reconstruct a UserConfig from the session so pages
  // that need a UserConfig work for password-authenticated admins.
  if (session.userId.startsWith('pwd:')) {
    return {
      user_id: session.userId,
      name: session.displayName,
      email: '',
      role: session.role,
      allowed_entities: session.allowedEntities,
      allowed_pages: session.allowedPages,
    };
  }
  throw new Error('User not found');
}
