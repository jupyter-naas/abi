/**
 * Auth session helpers shared by the auth store and route guards.
 */

export interface PersistedAuthSnapshot {
  user?: unknown;
  isAuthenticated?: boolean;
}

/** Set the lightweight auth flag cookie used by edge middleware. */
export function setAuthFlagCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = 'nexus-auth-flag=true; path=/; max-age=2592000; SameSite=Lax';
}

/** Clear the auth flag cookie so middleware stops treating the user as signed in. */
export function clearAuthFlagCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = 'nexus-auth-flag=; path=/; max-age=0; SameSite=Lax';
}

/**
 * Zustand persist merge: take the user and the signed-in flag from storage and
 * nothing else. A snapshot an older version wrote may hold tokens of the login
 * Nexus no longer has: they are dropped, never adopted.
 */
export function mergeAuthPersistedState<T extends PersistedAuthSnapshot>(
  persisted: unknown,
  current: T,
): T {
  const stored = (persisted ?? {}) as PersistedAuthSnapshot;
  return {
    ...current,
    user: stored.user ?? current.user,
    isAuthenticated: Boolean(stored.isAuthenticated),
  } as T;
}

/** A path on this app to land on after sign-in: never another origin. */
export function safeNextPath(value: string | null | undefined): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return '/';
  if (/[\u0000-\u001f]/.test(value)) return '/';
  return value;
}
