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
 * Whether a visitor landing on the magic-link page should be sent straight to
 * their destination instead of being asked to confirm.
 *
 * A token in the URL always wins. `isAuthenticated` is rehydrated from
 * localStorage and routinely outlives the access token it was stored with, so
 * trusting it here would redirect the user away before the freshly-emailed
 * token is exchanged — the link silently does nothing and they bounce back to
 * the login page, which reads to users as a caching bug.
 */
export function shouldSkipMagicLinkConfirmation(
  token: string | null | undefined,
  isAuthenticated: boolean,
): boolean {
  if (token) return false;
  return isAuthenticated;
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
