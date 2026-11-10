/**
 * Authentication store for NEXUS.
 *
 * Sign-in belongs to the engine's identity providers (OIDC, authorization code
 * with PKCE). The API holds the session behind an httpOnly cookie; this store
 * keeps no token at all, only the signed-in user and the session's CSRF token,
 * which stays in memory and is never persisted.
 */

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { discardDeferredStorage } from '@/lib/deferred-storage';
import { clearAuthFlagCookie, mergeAuthPersistedState, setAuthFlagCookie } from '@/lib/auth-session';
import { getSafeStorage } from '@/lib/safe-storage';
import { clearViewFlag, setViewFlag, viewFlagActive, readViewFlag } from '@/lib/view-flag';
import {
  announceViewRefusal,
  navigation,
  parseView,
  viewRefusalMessage,
  type ViewAs,
} from '@/lib/view-model';

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  organization?: string;
  job_title?: string;
  bio?: string;
  linkedin_url?: string;
  github_handle?: string;
  is_superadmin?: boolean;
  createdAt: Date;
}

export interface AuthState {
  // State
  // Who the pages show: the signed-in user, or the person during a view.
  user: User | null;
  // During a view: the view the server keeps on this session, and who is viewing.
  // Null otherwise. The session (CSRF) stays the viewer's, `user` is the person's.
  view: ViewAs | null;
  viewer: User | null;
  // The identity provider of the session (the banner names it when its groups are missing).
  provider: string | null;
  // In memory: sent as X-CSRF-Token on every request that changes state.
  csrfToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  logout: () => void;
  setUser: (user: User | null) => void;
  clearError: () => void;
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
    (set, get) => ({
      // Initial state
      user: null,
      view: null,
      viewer: null,
      provider: null,
      csrfToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Logout - clears auth state and ALL persisted store data
      logout: () => {
        clearAuthFlagCookie();
        // The sign-out ends the view on the server; the browser forgets it too.
        clearViewFlag();
        const { csrfToken } = get();
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

        set({
          user: null,
          view: null,
          viewer: null,
          provider: null,
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
        // In a view `localStorage` is memory: the browser's own is kept aside for this clearing.
        const browserStorage =
          (typeof window !== 'undefined' &&
            (window as { __nexusRealLocalStorage?: Storage }).__nexusRealLocalStorage) ||
          undefined;
        for (const key of storeKeys) {
          try { (browserStorage ?? localStorage).removeItem(key); } catch { /* SSR safe */ }
        }
      },

      // Set user manually
      setUser: (user: User | null) => {
        set({ user, isAuthenticated: !!user });
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },

      // Re-read the session the API holds: it refreshes it at the provider.
      checkAuth: async (): Promise<boolean> => {
        const adopted = await get().adoptCookieSession();
        return adopted || get().isAuthenticated;
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
            clearViewFlag();
            if (get().isAuthenticated) {
              clearAuthFlagCookie();
              set({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
            }
            return false;
          }
          if (!response.ok) return false;
          const data = await response.json();
          const user = data.user ?? {};
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);
          const signedIn = { ...user, avatar: normalizeAvatar(user.avatar) } as User;
          const view = parseView(data.view);
          setAuthFlagCookie();
          // The browser and the server must agree on a view before anything is shown: the stores read
          // the flag when they are created, so a view the browser did not know (another tab, cleared
          // cookies), or one that ended, is followed by a reload with the flag set or cleared.
          const flag = readViewFlag();
          if (view && !flag) {
            setViewFlag({ workspaceId: view.workspace.id, returnTo: null }, view.ends_at);
            navigation.reload();
            return true;
          }
          if (!view && flag) {
            clearViewFlag();
            navigation.reload();
            return true;
          }
          const shown = view ? await personOf(apiBase, view, normalizeAvatar) : signedIn;
          set({
            user: shown,
            view,
            viewer: view ? signedIn : null,
            provider: typeof data.provider === 'string' ? data.provider : null,
            csrfToken: typeof data.csrf_token === 'string' ? data.csrf_token : null,
            isAuthenticated: true,
            error: null,
          });
          return true;
        } catch {
          return false;
        }
      },
    }),
    {
      name: 'nexus-auth',
      storage: createJSONStorage(() => getSafeStorage()),
      merge: mergeAuthPersistedState,
      partialize: (state) => persistedAuthState(state),
    }
  )
);

/**
 * The person of a view as the server answers them (`GET /api/auth/me` runs as the person in a view),
 * or the little the view itself says when that fails: never the viewer.
 */
async function personOf(
  apiBase: string,
  view: ViewAs,
  normalizeAvatar: (a?: string) => string | undefined,
): Promise<User> {
  try {
    const response = await fetch(`${apiBase}/api/auth/me`, { credentials: 'include', cache: 'no-store' });
    if (response.ok) {
      const person = await response.json();
      return { ...person, avatar: normalizeAvatar(person.avatar) } as User;
    }
  } catch {
    // fall back to the view's own words
  }
  return { id: view.person.id, email: '', name: view.person.name, createdAt: new Date() };
}

/** What is persisted: the user only, never a token and never the CSRF token. */
export function persistedAuthState(state: Pick<AuthState, 'user' | 'isAuthenticated'>) {
  // During a view `user` is the person: nothing of them is written.
  if (viewFlagActive()) return {};
  return { user: state.user, isAuthenticated: state.isAuthenticated };
}

const COOKIE_SESSION = 'cookie-session';

/**
 * A value that names the current session: a marker while signed in, null when
 * signed out. For effects that follow the session.
 */
export function selectSession(state: Pick<AuthState, 'isAuthenticated'>): string | null {
  return state.isAuthenticated ? COOKIE_SESSION : null;
}

/** Whether a user is signed in. */
export function hasSession(state: Pick<AuthState, 'isAuthenticated'> = useAuthStore.getState()): boolean {
  return state.isAuthenticated;
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
 * Auth header for API requests: the session's CSRF token on a request that
 * changes state. Pair it with `credentials: authCredentials()`.
 */
export function getAuthHeader(method: string = 'GET'): Record<string, string> {
  const { csrfToken } = useAuthStore.getState();
  if (csrfToken && !SAFE_METHODS.has(method.toUpperCase())) {
    return { [CSRF_HEADER]: csrfToken };
  }
  return {};
}

/** The session is the API's cookie: requests must include it. */
export function authCredentials(): RequestCredentials {
  return 'include';
}

/** `init` with this session's credentials, the CSRF token loaded when needed. */
export async function withAuth(init: RequestInit = {}): Promise<RequestInit> {
  const method = (init.method || 'GET').toUpperCase();
  const state = useAuthStore.getState();
  if (!state.csrfToken && !SAFE_METHODS.has(method)) {
    await state.adoptCookieSession();
  }
  const headers = new Headers(init.headers);
  for (const [name, value] of Object.entries(getAuthHeader(method))) headers.set(name, value);
  return { ...init, headers, credentials: authCredentials() };
}

/**
 * Authenticated fetch wrapper: the session cookie, the CSRF token on changes.
 * On a 401 the session is re-read once before giving up and signing out.
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
  const makeRequest = () =>
    fetchWithSettingsCacheFallback(wantSettingsCache, (useCache) => {
      const headers = new Headers(options.headers);
      const { csrfToken } = useAuthStore.getState();
      if (csrfToken && !SAFE_METHODS.has(method)) headers.set(CSRF_HEADER, csrfToken);
      if (useCache) headers.set(SETTINGS_CACHE_HEADER, '1');
      return fetch(fullUrl, { ...options, headers, credentials: 'include' as const });
    });

  // Surface in-flight activity to the UI (e.g. ApiStatusIndicator pulses while busy).
  const { useNetworkActivityStore } = await import('./network-activity');
  const { begin, end } = useNetworkActivityStore.getState();
  begin();

  try {
    const response = await sessionFetch(method, makeRequest);
    if (useAuthStore.getState().view) {
      const refusal = await viewRefusalMessage(response);
      if (refusal) announceViewRefusal(refusal);
    }
    return response;
  } finally {
    end();
  }
}

/** A request of the session: the CSRF token loaded first for a change, the
 * session re-read once on a 401 or 403 (another tab, a restart), else signed out. */
async function sessionFetch(
  method: string,
  makeRequest: () => Promise<Response>,
): Promise<Response> {
  const store = useAuthStore.getState();
  if (!store.csrfToken && !SAFE_METHODS.has(method)) await store.adoptCookieSession();
  const response = await makeRequest();
  if (response.status !== 401 && !(response.status === 403 && !SAFE_METHODS.has(method))) {
    return response;
  }
  // The view's refusal is final: re-reading the session cannot change it.
  if (response.status === 403 && (await viewRefusalMessage(response))) return response;
  if (await useAuthStore.getState().adoptCookieSession()) {
    const retried = await makeRequest();
    if (retried.status !== 401) return retried;
  }
  if (response.status === 403) return response;
  // The session could not be re-read (the API is failing, or offline): it may
  // still be good, so keep it. Only an API that no longer knows it ends it.
  if (useAuthStore.getState().isAuthenticated) return response;
  useAuthStore.getState().logout();
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth/')) {
    window.location.href = '/auth/login';
  }
  return response;
}
