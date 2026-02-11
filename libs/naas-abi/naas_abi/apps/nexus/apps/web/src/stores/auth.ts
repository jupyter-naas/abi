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
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string, name: string) => Promise<boolean>;
  logout: () => void;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  clearError: () => void;
  checkAuth: () => Promise<boolean>;
}

import { getApiUrl } from '@/lib/config';

const API_BASE = getApiUrl();

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      
  // Login with email/password
  login: async (email: string, password: string): Promise<boolean> => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include', // Important: allows cookies to be set
            body: JSON.stringify({ email, password }),
          });
          
          if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Login failed');
          }
          
          const data = await response.json();
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${API_BASE}${a}` : a);
          
          // Set auth flag cookie for middleware
          document.cookie = 'nexus-auth-flag=true; path=/; max-age=2592000'; // 30 days
          
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
            error: error instanceof Error ? error.message : 'Login failed',
          });
          return false;
        }
      },
      
      // Register new account
      register: async (email: string, password: string, name: string): Promise<boolean> => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include', // Important: allows cookies to be set
            body: JSON.stringify({ email, password, name }),
          });
          
          if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Registration failed');
          }
          
          const data = await response.json();
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${API_BASE}${a}` : a);
          
          // Set auth flag cookie for middleware
          document.cookie = 'nexus-auth-flag=true; path=/; max-age=2592000'; // 30 days
          
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
            error: error instanceof Error ? error.message : 'Registration failed',
          });
          return false;
        }
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
          const response = await fetch(`${API_BASE}/api/auth/me`, {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });
          
          if (!response.ok) {
            set({ isAuthenticated: false, user: null, token: null });
            return false;
          }
          
          const user = await response.json();
          const normalizeAvatar = (a?: string) => (a && a.startsWith('/') ? `${API_BASE}${a}` : a);
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
  
  // Prepend API_BASE if URL is relative
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
  
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
      window.location.href = '/login';
    }
  }
  
  return response;
}
