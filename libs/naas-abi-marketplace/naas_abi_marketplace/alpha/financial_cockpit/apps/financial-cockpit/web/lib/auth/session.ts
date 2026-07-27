import { cookies } from 'next/headers';

import type { PageId, SessionPayload, UserConfig } from '@/lib/types';
import { normalizePageId } from '@/lib/types';
import { listAdminUsers, getUserById } from '@/lib/server/financeUsers';
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

export async function getSession(): Promise<SessionPayload | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;
  if (!token) {
    return null;
  }
  return verifySessionToken(token);
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
 * The session JWT snapshots the role at login time; read live config so a
 * role granted in config.yaml applies without forcing a re-login. Falls back
 * to the JWT role for synthetic sessions with no config user (`pwd:*`).
 */
export async function isAdminSession(session: SessionPayload): Promise<boolean> {
  const configRole = listAdminUsers().find((u) => u.user_id === session.userId)?.role;
  return (configRole ?? session.role) === 'admin';
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
