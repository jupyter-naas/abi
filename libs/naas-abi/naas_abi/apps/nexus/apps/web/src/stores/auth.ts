/**
 * Authentication store for NEXUS.
 * Manages user session, tokens, and auth state.
 *
 * Two kinds of session:
 * - `bearer`: the built-in login (password, magic link, code). Its tokens are
 *   kept here and persisted, as before.
 * - `cookie`: a sign-in through an identity provider. The API holds the
 *   session behind an httpOnly cookie; this store keeps no token at all, only
 *   the session's CSRF token, in memory (never persisted).
 */

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { discardDeferredStorage } from '@/lib/deferred-storage';
import { clearAuthFlagCookie, mergeAuthPersistedState, setAuthFlagCookie, shouldRefreshAccessToken } from '@/lib/auth-session';
import { getSafeStorage } from '@/lib/safe-storage';

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  company?: string;
  role?: string;
  bio?: string;
  is_superadmin?: boolean;
  createdAt: Date;
}

export type SessionKind = 'bearer' | 'cookie';

export interface AuthState {
  // State
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  sessionKind: SessionKind | null;
  // Cookie sessions only, in memory: sent as X-CSRF-Token on every change.
  csrfToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  requestMagicLink: (email: string) => Promise<boolean>;
  verifyMagicLink: (token: string) => Promise<boolean>;
  verifyOtp: (email: string, code: string) => Promise<string | null>;
  login: (email: string, password: string) => Promise<string | null>;
  register: (email: string, password: string, name: string) => Promise<boolean>;
  logout: () => void;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  clearError: () => void;
  refreshAccessToken: () => Promise<boolean>;
  checkAuth: () => Promise<boolean>;
  // Identity providers: which one an email goes to, start a sign-in there,
  // and adopt the cookie session the API set on the way back.
  routeLogin: (email: string) => Promise<string | null>;
  signInWithProvider: (options: { provider?: string; email?: string; next?: string }) => void;
  adoptCookieSession: () => Promise<boolean>;
}

const CSRF_HEADER = 'X-CSRF-Token';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

import { getApiUrl } from '@/lib/config';
import {
  SETTINGS_CACHE_HEADER,
  fetchWithSettingsCacheFallback,
  shouldUseSettingsCache,
} from '@/lib/settings-cache';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => {
      let refreshPromise: Promise<boolean> | null = null;
      return {
      // Initial state
      user: null,
      token: null,
      refreshToken: null,
      sessionKind: null,
      csrfToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

  requestMagicLink: async (email: string): Promise<boolean> => {
        set({ isLoading: true, error: null });

        try {
          const apiBase = getApiUrl();
          const response = await fetch(`${apiBase}/api/auth/magic-link/request`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email }),
          });

          if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to send magic link');
          }

          set({ isLoading: false, error: null });

          return true;
        } catch (error) {
          set({
            isLoading: false,
            error: error instanceof Error ? error.message : 'Failed to send magic link',
          });
          return false;
        }
      },

      verifyMagicLink: async (token: string): Promise<boolean> => {
        set({ isLoading: true, error: null });

        try {
          const apiBase = getApiUrl();
          const response = await fetch(`${apiBase}/api/auth/magic-link/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ token }),
          });

          if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Magic link verification failed');
          }

          const data = await response.json();
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);

          setAuthFlagCookie();

          set({
            user: { ...data.user, avatar: normalizeAvatar(data.user?.avatar) },
            token: data.access_token,
            refreshToken: data.refresh_token ?? null,
            sessionKind: 'bearer',
            csrfToken: null,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          return true;
        } catch (error) {
          clearAuthFlagCookie();
          set({
            isLoading: false,
            error: error instanceof Error ? error.message : 'Magic link verification failed',
          });
          return false;
        }
      },

      verifyOtp: async (email: string, code: string): Promise<string | null> => {
        set({ isLoading: true, error: null });

        try {
          const apiBase = getApiUrl();
          const response = await fetch(`${apiBase}/api/auth/otp/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, code }),
          });

          if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Invalid or expired sign-in code');
          }

          const data = await response.json();
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);

          setAuthFlagCookie();

          set({
            user: { ...data.user, avatar: normalizeAvatar(data.user?.avatar) },
            token: data.access_token,
            refreshToken: data.refresh_token ?? null,
            sessionKind: 'bearer',
            csrfToken: null,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          try {
            const wsResponse = await fetch(`${apiBase}/api/workspaces`, {
              headers: { Authorization: `Bearer ${data.access_token}` },
            });
            if (wsResponse.ok) {
              const workspaces = await wsResponse.json();
              if (Array.isArray(workspaces) && workspaces.length > 0) {
                const sorted = [...workspaces].sort((a, b) => {
                  const ac = a.created_at ?? '';
                  const bc = b.created_at ?? '';
                  if (ac !== bc) return ac < bc ? -1 : 1;
                  return (a.slug ?? '').localeCompare(b.slug ?? '');
                });
                return sorted[0].id;
              }
            }
          } catch {
            // Non-fatal: fall back to middleware redirect
          }

          return null;
        } catch (error) {
          clearAuthFlagCookie();
          set({
            isLoading: false,
            error: error instanceof Error ? error.message : 'Invalid or expired sign-in code',
          });
          return null;
        }
      },

      login: async (email: string, password: string): Promise<string | null> => {
        set({ isLoading: true, error: null });
        try {
          const apiBase = getApiUrl();
          const response = await fetch(`${apiBase}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Invalid email or password');
          }

          const data = await response.json();
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);

          setAuthFlagCookie();

          set({
            user: { ...data.user, avatar: normalizeAvatar(data.user?.avatar) },
            token: data.access_token,
            refreshToken: data.refresh_token ?? null,
            sessionKind: 'bearer',
            csrfToken: null,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          // Return a workspace ID so the caller can redirect directly, bypassing middleware slug guessing.
          // Sort by created_at then slug for stable ordering across requests.
          try {
            const wsResponse = await fetch(`${apiBase}/api/workspaces`, {
              headers: { Authorization: `Bearer ${data.access_token}` },
            });
            if (wsResponse.ok) {
              const workspaces = await wsResponse.json();
              if (Array.isArray(workspaces) && workspaces.length > 0) {
                const sorted = [...workspaces].sort((a, b) => {
                  const ac = a.created_at ?? '';
                  const bc = b.created_at ?? '';
                  if (ac !== bc) return ac < bc ? -1 : 1;
                  return (a.slug ?? '').localeCompare(b.slug ?? '');
                });
                return sorted[0].id;
              }
            }
          } catch {
            // Non-fatal: fall back to middleware redirect
          }

          return null;
        } catch (error) {
          set({
            isLoading: false,
            error: error instanceof Error ? error.message : 'Invalid email or password',
          });
          return null;
        }
      },

      register: async (email: string, _password: string, _name: string): Promise<boolean> => {
        return get().requestMagicLink(email);
      },

      // Logout - clears auth state and ALL persisted store data
      logout: () => {
        clearAuthFlagCookie();
        const { sessionKind, csrfToken } = get();
        if (sessionKind === 'cookie') {
          // The API ends the session; the provider may end its own too.
          void fetch(`${getApiUrl()}/api/auth/oidc/logout`, {
            method: 'POST',
            credentials: 'include',
            headers: csrfToken ? { [CSRF_HEADER]: csrfToken } : {},
          })
            .then((r) => (r.ok ? r.json() : null))
            .then((data) => {
              if (data?.end_session_url && typeof window !== 'undefined') {
                window.location.href = data.end_session_url;
              }
            })
            .catch(() => undefined);
        }

        set({
          user: null,
          token: null,
          refreshToken: null,
          sessionKind: null,
          csrfToken: null,
          isAuthenticated: false,
          error: null,
        });
        // Clear all persisted stores to prevent data leakage between users
        const storeKeys = [
          'nexus-workspace-storage',
          'nexus-integrations',
          'nexus-agents',
          'nexus-skills',
          'nexus-search',
          'nexus-ontology',
          'nexus-knowledge-graph',
          'nexus-servers',
        ];
        // Queued deferred writes would otherwise re-create these keys.
        discardDeferredStorage(storeKeys);
        for (const key of storeKeys) {
          try { localStorage.removeItem(key); } catch { /* SSR safe */ }
        }
      },

      // Set user manually
      setUser: (user: User | null) => {
        set({ user, isAuthenticated: !!user });
      },

      // Set token manually
      setToken: (token: string | null) => {
        set({ token });
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },

      // Share rotation within a tab, and serialize it across tabs where supported.
      refreshAccessToken: (): Promise<boolean> => {
        // A cookie session is refreshed by the API, at the provider: re-read it.
        if (get().sessionKind === 'cookie') return get().adoptCookieSession();
        if (refreshPromise) return refreshPromise;
        const originalRefreshToken = get().refreshToken;
        const refresh = async (): Promise<boolean> => {
          // Another tab may have rotated or logged out while we waited for the lock.
          syncPersistedAuthSession();
          const { refreshToken } = get();
          if (!refreshToken) return false;
          if (refreshToken !== originalRefreshToken) return Boolean(get().token);

          try {
            const response = await fetch(`${getApiUrl()}/api/auth/refresh`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ refresh_token: refreshToken }),
              signal: AbortSignal.timeout(15000),
            });
            // A login/logout during this request owns the newer state.
            syncPersistedAuthSession();
            if (get().refreshToken !== refreshToken) return false;
            if (!response.ok) {
              if (response.status === 401 || response.status === 403) get().logout();
              return false;
            }
            const data = await response.json();
            if (get().refreshToken !== refreshToken) return false;
            if (!data.access_token || !data.refresh_token) return false;
            set({ token: data.access_token, refreshToken: data.refresh_token, isAuthenticated: true });
            setAuthFlagCookie();
            return true;
          } catch {
            // Offline, timeout, or server failure: keep credentials for the next attempt.
            return false;
          }
        };
        refreshPromise = (async () => {
          if (typeof navigator !== 'undefined' && navigator.locks) {
            return await navigator.locks.request('nexus-auth-refresh', refresh);
          }
          return await refresh();
        })().finally(() => { refreshPromise = null; });
        return refreshPromise;
      },

      // Check if current token is valid; silently refreshes if expired.
      checkAuth: async (): Promise<boolean> => {
        if (get().sessionKind === 'cookie') {
          const adopted = await get().adoptCookieSession();
          return adopted || get().isAuthenticated;
        }
        const { token } = get();

        // No access token — try to recover via refresh token
        if (!token) {
          const refreshed = await get().refreshAccessToken();
          if (!refreshed) {
            return get().isAuthenticated;
          }
        }

        try {
          const apiBase = getApiUrl();
          const currentToken = get().token;
          const response = await fetch(`${apiBase}/api/auth/me`, {
            headers: {
              'Authorization': `Bearer ${currentToken}`,
            },
          });

          if (get().token !== currentToken) return get().isAuthenticated;
          if (response.status === 401) {
            // Access token rejected — try refresh once
            const refreshed = await get().refreshAccessToken();
            if (!refreshed) {
              if (!get().refreshToken) get().logout();
              return get().isAuthenticated;
            }
            // Retry /me with the new token
            const newToken = get().token;
            const retryResponse = await fetch(`${apiBase}/api/auth/me`, {
              headers: { 'Authorization': `Bearer ${newToken}` },
            });
            if (get().token !== newToken) return get().isAuthenticated;
            if (!retryResponse.ok) {
              if (retryResponse.status === 401 || retryResponse.status === 403) get().logout();
              return get().isAuthenticated;
            }
            const retryUser = await retryResponse.json();
            if (get().token !== newToken) return get().isAuthenticated;
            const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);
            setAuthFlagCookie();
            set({ user: { ...retryUser, avatar: normalizeAvatar(retryUser?.avatar) }, isAuthenticated: true });
            return true;
          }

          if (!response.ok) {
            // Non-auth server error — preserve existing auth state (e.g. server temporarily down)
            return get().isAuthenticated;
          }

          const user = await response.json();
          if (get().token !== currentToken) return get().isAuthenticated;
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);
          setAuthFlagCookie();
          set({ user: { ...user, avatar: normalizeAvatar(user?.avatar) }, isAuthenticated: true });
          return true;
        } catch {
          // Network error — preserve existing auth state for offline resilience
          return get().isAuthenticated;
        }
      },

      routeLogin: async (email: string): Promise<string | null> => {
        try {
          const response = await fetch(`${getApiUrl()}/api/auth/oidc/route`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
          });
          if (!response.ok) return null;
          const data = await response.json();
          return typeof data.provider === 'string' && data.provider ? data.provider : null;
        } catch {
          return null;
        }
      },

      signInWithProvider: ({ provider, email, next }: { provider?: string; email?: string; next?: string }) => {
        if (typeof window === 'undefined') return;
        window.location.href = providerLoginUrl({ provider, email, next });
      },

      adoptCookieSession: async (): Promise<boolean> => {
        const apiBase = getApiUrl();
        try {
          const response = await fetch(`${apiBase}/api/auth/oidc/session`, {
            credentials: 'include',
            cache: 'no-store',
          });
          if (response.status === 401) {
            if (get().sessionKind === 'cookie') {
              clearAuthFlagCookie();
              set({ user: null, sessionKind: null, csrfToken: null, isAuthenticated: false });
            }
            return false;
          }
          if (!response.ok) return false;
          const data = await response.json();
          const user = data.user ?? {};
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);
          setAuthFlagCookie();
          set({
            user: { ...user, avatar: normalizeAvatar(user.avatar) },
            token: null,
            refreshToken: null,
            sessionKind: 'cookie',
            csrfToken: typeof data.csrf_token === 'string' ? data.csrf_token : null,
            isAuthenticated: true,
            error: null,
          });
          return true;
        } catch {
          return false;
        }
      },
    };
    },
    {
      name: 'nexus-auth',
      storage: createJSONStorage(() => getSafeStorage()),
      merge: mergeAuthPersistedState,
      partialize: (state) => persistedAuthState(state),
    }
  )
);

/** What is persisted: never a token of a cookie session, never a CSRF token. */
export function persistedAuthState(state: Pick<AuthState, 'user' | 'token' | 'refreshToken' | 'sessionKind' | 'isAuthenticated'>) {
  if (state.sessionKind === 'cookie') {
    return { user: state.user, sessionKind: state.sessionKind, isAuthenticated: state.isAuthenticated };
  }
  return {
    user: state.user,
    token: state.token,
    refreshToken: state.refreshToken,
    sessionKind: state.sessionKind,
    isAuthenticated: state.isAuthenticated,
  };
}

const COOKIE_SESSION = 'cookie-session';

/**
 * A value that names the current session: the bearer token, a marker for a
 * cookie session, null when signed out. For effects that follow the session.
 */
export function selectSession(state: Pick<AuthState, 'token' | 'sessionKind' | 'isAuthenticated'>): string | null {
  if (state.token) return state.token;
  return state.sessionKind === 'cookie' && state.isAuthenticated ? COOKIE_SESSION : null;
}

/** Whether a user is signed in: a bearer token, or a cookie session. */
export function hasSession(state: Pick<AuthState, 'token' | 'sessionKind' | 'isAuthenticated'> = useAuthStore.getState()): boolean {
  return Boolean(state.token) || (state.sessionKind === 'cookie' && state.isAuthenticated);
}

/** The API's URL that starts a sign-in at an identity provider. */
export function providerLoginUrl({ provider, email, next }: { provider?: string; email?: string; next?: string }): string {
  const params = new URLSearchParams();
  if (provider) params.set('provider', provider);
  if (email) params.set('email', email);
  if (next) params.set('next', next);
  return `${getApiUrl()}/api/auth/oidc/login?${params}`;
}

/**
 * Get auth header for API requests: the bearer token, or for a cookie session
 * the CSRF token on a request that changes state. Pair it with
 * `credentials: authCredentials()`.
 */
export function getAuthHeader(method: string = 'GET'): Record<string, string> {
  const { token, sessionKind, csrfToken } = useAuthStore.getState();
  if (token) return { 'Authorization': `Bearer ${token}` };
  if (sessionKind === 'cookie' && csrfToken && !SAFE_METHODS.has(method.toUpperCase())) {
    return { [CSRF_HEADER]: csrfToken };
  }
  return {};
}

/** Cookie sessions travel as the API's cookie: requests must include it. */
export function authCredentials(): RequestCredentials | undefined {
  return useAuthStore.getState().sessionKind === 'cookie' ? 'include' : undefined;
}

/** `init` with this session's credentials, the CSRF token loaded when needed. */
export async function withAuth(init: RequestInit = {}): Promise<RequestInit> {
  const method = (init.method || 'GET').toUpperCase();
  const state = useAuthStore.getState();
  if (state.sessionKind === 'cookie' && !state.csrfToken && !SAFE_METHODS.has(method)) {
    await state.adoptCookieSession();
  }
  const headers = new Headers(init.headers);
  for (const [name, value] of Object.entries(getAuthHeader(method))) headers.set(name, value);
  const credentials = authCredentials() ?? init.credentials;
  return { ...init, headers, ...(credentials ? { credentials } : {}) };
}

/**
 * Authenticated fetch wrapper.
 * On 401, attempts a silent token refresh before giving up and logging out.
 */
export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const apiBase = getApiUrl();

  // Prepend API_BASE if URL is relative
  const fullUrl = url.startsWith('http') ? url : `${apiBase}${url}`;

  // Settings pages read through the backend's 24h settings cache (see lib/settings-cache).
  const wantSettingsCache =
    typeof window !== 'undefined' &&
    fullUrl.startsWith(apiBase) &&
    !new Headers(options.headers).has(SETTINGS_CACHE_HEADER) &&
    shouldUseSettingsCache(window.location.pathname, options.method);

  const method = (options.method || 'GET').toUpperCase();
  const makeRequest = (tok: string | null) =>
    fetchWithSettingsCacheFallback(wantSettingsCache, (useCache) => {
      const headers = new Headers(options.headers);
      if (tok) headers.set('Authorization', `Bearer ${tok}`);
      const { sessionKind, csrfToken } = useAuthStore.getState();
      const cookieSession = !tok && sessionKind === 'cookie';
      if (cookieSession && csrfToken && !SAFE_METHODS.has(method)) headers.set(CSRF_HEADER, csrfToken);
      if (useCache) headers.set(SETTINGS_CACHE_HEADER, '1');
      return fetch(fullUrl, { ...options, headers, ...(cookieSession ? { credentials: 'include' as const } : {}) });
    });

  // Surface in-flight activity to the UI (e.g. ApiStatusIndicator pulses while busy).
  const { useNetworkActivityStore } = await import('./network-activity');
  const { begin, end } = useNetworkActivityStore.getState();
  begin();

  try {
    if (useAuthStore.getState().sessionKind === 'cookie') {
      return await cookieSessionFetch(method, makeRequest);
    }
    if (shouldRefreshAccessToken(useAuthStore.getState().token)) {
      await useAuthStore.getState().refreshAccessToken();
    }
    const requestToken = useAuthStore.getState().token;
    const response = await makeRequest(requestToken);

    if (response.status === 401) {
      // Try a silent token refresh
      const refreshed = useAuthStore.getState().token !== requestToken
        ? Boolean(useAuthStore.getState().token)
        : await useAuthStore.getState().refreshAccessToken();
      if (refreshed) {
        // Retry the original request with the new token
        return await makeRequest(useAuthStore.getState().token);
      }

      // Temporary refresh failures must not destroy a recoverable session.
      if (useAuthStore.getState().refreshToken) return response;

      useAuthStore.getState().logout();
      // Skip redirect if already on an auth route — otherwise we trigger a
      // reload loop with stores that auto-fetch on hydration.
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
        window.location.href = '/auth/login';
      }
    }

    return response;
  } finally {
    end();
  }
}

/** A cookie session's request: the CSRF token loaded first for a change, the
 * session re-read once on a 401 or 403 (another tab, a restart), else signed out. */
async function cookieSessionFetch(
  method: string,
  makeRequest: (tok: string | null) => Promise<Response>,
): Promise<Response> {
  const store = useAuthStore.getState();
  if (!store.csrfToken && !SAFE_METHODS.has(method)) await store.adoptCookieSession();
  const response = await makeRequest(null);
  if (response.status !== 401 && !(response.status === 403 && !SAFE_METHODS.has(method))) {
    return response;
  }
  if (await useAuthStore.getState().adoptCookieSession()) {
    const retried = await makeRequest(null);
    if (retried.status !== 401) return retried;
  }
  if (response.status === 403) return response;
  useAuthStore.getState().logout();
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
    window.location.href = '/auth/login';
  }
  return response;
}

/** Adopt rotations and explicit logout from other tabs before using shared credentials. */
export function syncPersistedAuthSession(): void {
  try {
    const raw = getSafeStorage().getItem('nexus-auth');
    if (!raw) return;
    const { state } = JSON.parse(raw);
    if (!state || !('refreshToken' in state)) return;
    const current = useAuthStore.getState();
    if (current.token === state.token && current.refreshToken === state.refreshToken) return;
    useAuthStore.setState({
      user: state.user ?? null,
      token: state.token ?? null,
      refreshToken: state.refreshToken ?? null,
      isAuthenticated: Boolean(state.isAuthenticated),
    });
    if (state.isAuthenticated) setAuthFlagCookie();
    else clearAuthFlagCookie();
  } catch {
    // An unreadable storage snapshot must not replace a live session.
  }
}
