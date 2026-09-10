/**
 * Authentication store for NEXUS.
 * Manages user session, tokens, and auth state.
 */

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
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

export interface AuthState {
  // State
  user: User | null;
  token: string | null;
  refreshToken: string | null;
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
}

import { getApiUrl } from '@/lib/config';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => {
      let refreshPromise: Promise<boolean> | null = null;
      return {
      // Initial state
      user: null,
      token: null,
      refreshToken: null,
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

        set({
          user: null,
          token: null,
          refreshToken: null,
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
    };
    },
    {
      name: 'nexus-auth',
      storage: createJSONStorage(() => getSafeStorage()),
      merge: mergeAuthPersistedState,
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

/**
 * Get auth header for API requests
 */
export function getAuthHeader(): Record<string, string> {
  const token = useAuthStore.getState().token;
  if (!token) return {};
  return { 'Authorization': `Bearer ${token}` };
}

/**
 * Authenticated fetch wrapper.
 * On 401, attempts a silent token refresh before giving up and logging out.
 */
export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const apiBase = getApiUrl();

  // Prepend API_BASE if URL is relative
  const fullUrl = url.startsWith('http') ? url : `${apiBase}${url}`;

  const makeRequest = (tok: string | null) => {
    const headers = new Headers(options.headers);
    if (tok) headers.set('Authorization', `Bearer ${tok}`);
    return fetch(fullUrl, { ...options, headers });
  };

  // Surface in-flight activity to the UI (e.g. ApiStatusIndicator pulses while busy).
  const { useNetworkActivityStore } = await import('./network-activity');
  const { begin, end } = useNetworkActivityStore.getState();
  begin();

  try {
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
