/**
 * Authentication store for NEXUS.
 * Manages user session, tokens, and auth state.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  company?: string;
  role?: string;
  bio?: string;
  createdAt: Date;
}

export interface AuthState {
  // State
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  requestMagicLink: (email: string) => Promise<boolean>;
  verifyMagicLink: (token: string) => Promise<boolean>;
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string, name: string) => Promise<boolean>;
  logout: () => void;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  clearError: () => void;
  checkAuth: () => Promise<boolean>;
}

import { getApiUrl } from '@/lib/config';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      token: null,
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

          document.cookie = 'nexus-auth-flag=true; path=/; max-age=2592000';

          set({
            user: { ...data.user, avatar: normalizeAvatar(data.user?.avatar) },
            token: data.access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
          
          return true;
        } catch (error) {
          set({
            isLoading: false,
            error: error instanceof Error ? error.message : 'Magic link verification failed',
          });
          return false;
        }
      },

      login: async (email: string, _password: string): Promise<boolean> => {
        return get().requestMagicLink(email);
      },

      register: async (email: string, _password: string, _name: string): Promise<boolean> => {
        return get().requestMagicLink(email);
      },
      
      // Logout - clears auth state and ALL persisted store data
      logout: () => {
        // Clear auth cookie
        document.cookie = 'nexus-auth-flag=; path=/; max-age=0';
        
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          error: null,
        });
        // Clear all persisted stores to prevent data leakage between users
        const storeKeys = [
          'nexus-workspace-storage',
          'nexus-integrations',
          'nexus-agents',
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
      
      // Check if current token is valid
      checkAuth: async (): Promise<boolean> => {
        const { token } = get();
        
        if (!token) {
          set({ isAuthenticated: false, user: null });
          return false;
        }
        
        try {
          const apiBase = getApiUrl();
          const response = await fetch(`${apiBase}/api/auth/me`, {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });
          
          if (!response.ok) {
            set({ isAuthenticated: false, user: null, token: null });
            return false;
          }
          
          const user = await response.json();
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${apiBase}${a}` : a);
          set({ user: { ...user, avatar: normalizeAvatar(user?.avatar) }, isAuthenticated: true });
          return true;
        } catch {
          set({ isAuthenticated: false, user: null, token: null });
          return false;
        }
      },
    }),
    {
      name: 'nexus-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
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
 * Authenticated fetch wrapper
 */
export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = useAuthStore.getState().token;
  const apiBase = getApiUrl();
  
  // Prepend API_BASE if URL is relative
  const fullUrl = url.startsWith('http') ? url : `${apiBase}${url}`;
  
  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  const response = await fetch(fullUrl, { ...options, headers });
  
  // Auto-logout on 401 to prevent stale token issues
    if (response.status === 401) {
      console.warn('Auth token expired or invalid, logging out...');
      useAuthStore.getState().logout();
      if (typeof window !== 'undefined') {
        window.location.href = '/auth/login';
      }
    }
  
  return response;
}
