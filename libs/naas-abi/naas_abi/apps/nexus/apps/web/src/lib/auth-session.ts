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
 * Local-dev auto-login.
 *
 * `abi dev up` hands the API the seeded admin credentials, which it serves
 * from /api/auth/config. The login page then submits the ordinary password
 * flow on the user's behalf — nothing is bypassed, the credentials still
 * have to be valid.
 *
 * Signing out has to stick, or the button is a no-op that loops you back in.
 * The suppression flag lives in localStorage (not sessionStorage) so it also
 * survives opening a new tab; it is cleared by a manual sign-in or by
 * ?autologin=1.
 */
const DEV_AUTOLOGIN_SUPPRESSED_KEY = 'nexus-dev-autologin-suppressed';

export interface DevAutoLoginCredentials {
  email: string;
  password: string;
}

/** Stop auto-login from re-signing-in until the user signs in manually. */
export function suppressDevAutoLogin(): void {
  try {
    localStorage.setItem(DEV_AUTOLOGIN_SUPPRESSED_KEY, 'true');
  } catch {
    /* SSR / blocked storage — worst case auto-login stays on */
  }
}

/** Re-arm auto-login (manual sign-in, or an explicit ?autologin=1). */
export function clearDevAutoLoginSuppression(): void {
  try {
    localStorage.removeItem(DEV_AUTOLOGIN_SUPPRESSED_KEY);
  } catch {
    /* SSR / blocked storage */
  }
}

export function isDevAutoLoginSuppressed(): boolean {
  try {
    return localStorage.getItem(DEV_AUTOLOGIN_SUPPRESSED_KEY) === 'true';
  } catch {
    return false;
  }
}

/**
 * Whether the login page should sign itself in.
 *
 * Kept pure and separate from the component so every gate is testable: the
 * server must have offered credentials, the user must not already be signed
 * in, must not have signed out, and must not have asked for the form via
 * ?nologin=1. `alreadyAttempted` makes this idempotent — a failed auto-login
 * must surface the error and leave the form alone, not retry on every
 * render.
 */
export function shouldDevAutoLogin(params: {
  credentials: DevAutoLoginCredentials | null;
  isAuthenticated: boolean;
  suppressed: boolean;
  optedOut: boolean;
  alreadyAttempted: boolean;
}): boolean {
  const { credentials, isAuthenticated, suppressed, optedOut, alreadyAttempted } = params;
  if (!credentials?.email || !credentials?.password) return false;
  if (isAuthenticated || suppressed || optedOut || alreadyAttempted) return false;
  return true;
}

/**
 * Pull dev auto-login credentials out of an /api/auth/config payload.
 * Returns null unless the server offered a complete pair.
 */
export function readDevAutoLoginConfig(payload: unknown): DevAutoLoginCredentials | null {
  if (!payload || typeof payload !== 'object') return null;
  const { dev_autologin_email: email, dev_autologin_password: password } =
    payload as Record<string, unknown>;
  if (typeof email !== 'string' || typeof password !== 'string') return null;
  if (!email || !password) return null;
  return { email, password };
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
