/**
 * Auth session helpers shared by the auth store and route guards.
 */

export interface PersistedAuthSnapshot {
  user?: unknown;
  token?: string | null;
  refreshToken?: string | null;
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
 * Zustand persist merge: keep an active in-memory session when storage failed
 * to persist tokens (blocked localStorage, hydration race after magic-link).
 */
export function mergeAuthPersistedState<T extends PersistedAuthSnapshot>(
  persisted: unknown,
  current: T,
): T {
  const stored = (persisted ?? {}) as PersistedAuthSnapshot;
  const liveHasSession = Boolean(current.token);
  const storedHasSession = Boolean(stored.token);

  if (liveHasSession && !storedHasSession) {
    return current;
  }

  return { ...current, ...stored } as T;
}
