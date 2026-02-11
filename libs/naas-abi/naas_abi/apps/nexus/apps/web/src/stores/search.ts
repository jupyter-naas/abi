'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authFetch } from './auth';
import { getApiUrl } from '@/lib/config';

export type SourceCategory = 'public' | 'private' | 'custom';

export interface SearchSource {
  id: string;
  name: string;
  category: SourceCategory;
  icon: string; // lucide icon name
  enabled: boolean;
  description?: string;
  // For API-based sources
  apiEndpoint?: string;
  apiKeyConfigKey?: string; // key in config.yaml or env
  // For custom sources
  dataType?: string; // e.g., 'contacts', 'projects'
  schema?: Record<string, string>; // field definitions
}

export interface SearchResult {
  id: string;
  sourceId: string;
  title: string;
  snippet: string;
  url?: string;
  metadata?: Record<string, unknown>;
  relevance?: number;
}

export interface SearchState {
  // Available sources
  sources: SearchSource[];
  
  // Search state
  query: string;
  results: SearchResult[];
  loading: boolean;
  error: string | null;
  
  // Recent searches
  recentSearches: string[];
  
  // Expanded categories in sidebar
  expandedCategories: SourceCategory[];
  
  // Actions
  setQuery: (query: string) => void;
  toggleSource: (sourceId: string) => void;
  toggleCategory: (category: SourceCategory) => void;
  addCustomSource: (source: Omit<SearchSource, 'id' | 'category'>) => void;
  removeCustomSource: (sourceId: string) => void;
  updateSource: (sourceId: string, updates: Partial<SearchSource>) => void;
  
  // Search actions
  search: (query: string) => Promise<void>;
  clearResults: () => void;
  addRecentSearch: (query: string) => void;
  clearRecentSearches: () => void;
}

// Default public sources
const defaultPublicSources: SearchSource[] = [
  {
    id: 'wikipedia',
    name: 'Wikipedia',
    category: 'public',
    icon: 'BookOpen',
    enabled: true,
    description: 'Search Wikipedia articles (free API)',
  },
  {
    id: 'duckduckgo',
    name: 'DuckDuckGo',
    category: 'public',
    icon: 'Search',
    enabled: true,
    description: 'DuckDuckGo instant answers (free API)',
  },
  {
    id: 'google',
    name: 'Google',
    category: 'public',
    icon: 'Globe',
    enabled: false,
    description: 'Search the web with Google (requires API key)',
    apiKeyConfigKey: 'GOOGLE_API_KEY',
  },
  {
    id: 'brave',
    name: 'Brave Search',
    category: 'public',
    icon: 'Shield',
    enabled: false,
    description: 'Privacy-focused web search (requires API key)',
    apiKeyConfigKey: 'BRAVE_API_KEY',
  },
];

// Default private sources
const defaultPrivateSources: SearchSource[] = [
  {
    id: 'conversations',
    name: 'Conversations',
    category: 'private',
    icon: 'MessageSquare',
    enabled: true,
    description: 'Search your chat history',
  },
  {
    id: 'files',
    name: 'Files',
    category: 'private',
    icon: 'FileCode',
    enabled: true,
    description: 'Search files in Lab',
  },
  {
    id: 'knowledge-graph',
    name: 'Knowledge Graph',
    category: 'private',
    icon: 'GitBranch',
    enabled: true,
    description: 'Search entities and relationships',
  },
  {
    id: 'ontology',
    name: 'Ontology',
    category: 'private',
    icon: 'Network',
    enabled: true,
    description: 'Search ontology definitions',
  },
];

// Example custom sources
const defaultCustomSources: SearchSource[] = [
  {
    id: 'contacts',
    name: 'Contacts',
    category: 'custom',
    icon: 'Users',
    enabled: false,
    description: 'Search your contacts',
    dataType: 'contacts',
  },
];

export const useSearchStore = create<SearchState>()(
  persist(
    (set, get) => ({
      // Initial state
      sources: [...defaultPublicSources, ...defaultPrivateSources, ...defaultCustomSources],
      query: '',
      results: [],
      loading: false,
      error: null,
      recentSearches: [],
      expandedCategories: ['public', 'private'],

      // Query
      setQuery: (query) => set({ query }),

      // Toggle source enabled/disabled
      toggleSource: (sourceId) =>
        set((state) => ({
          sources: state.sources.map((s) =>
            s.id === sourceId ? { ...s, enabled: !s.enabled } : s
          ),
        })),

      // Toggle category expansion in sidebar
      toggleCategory: (category) =>
        set((state) => ({
          expandedCategories: state.expandedCategories.includes(category)
            ? state.expandedCategories.filter((c) => c !== category)
            : [...state.expandedCategories, category],
        })),

      // Add custom source
      addCustomSource: (source) =>
        set((state) => ({
          sources: [
            ...state.sources,
            {
              ...source,
              id: `custom-${Date.now()}`,
              category: 'custom',
            },
          ],
        })),

      // Remove custom source
      removeCustomSource: (sourceId) =>
        set((state) => ({
          sources: state.sources.filter(
            (s) => s.id !== sourceId || s.category !== 'custom'
          ),
        })),

      // Update source
      updateSource: (sourceId, updates) =>
        set((state) => ({
          sources: state.sources.map((s) =>
            s.id === sourceId ? { ...s, ...updates } : s
          ),
        })),

      // Perform search across enabled sources
      search: async (query) => {
        if (!query.trim()) {
          set({ results: [], error: null });
          return;
        }

        set({ loading: true, error: null, query });
        get().addRecentSearch(query);

        try {
          const enabledSources = get().sources.filter((s) => s.enabled);
          const results: SearchResult[] = [];

          // Search each enabled source
          for (const source of enabledSources) {
            try {
              const sourceResults = await searchSource(source, query);
              results.push(...sourceResults);
            } catch (err) {
              console.error(`Search failed for source ${source.id}:`, err);
            }
          }

          // Sort by relevance
          results.sort((a, b) => (b.relevance || 0) - (a.relevance || 0));

          set({ results, loading: false });
        } catch (err) {
          set({
            error: err instanceof Error ? err.message : 'Search failed',
            loading: false,
          });
        }
      },

      clearResults: () => set({ results: [], query: '' }),

      addRecentSearch: (query) =>
        set((state) => {
          const filtered = state.recentSearches.filter((q) => q !== query);
          return {
            recentSearches: [query, ...filtered].slice(0, 10),
          };
        }),

      clearRecentSearches: () => set({ recentSearches: [] }),
    }),
    {
      name: 'nexus-search',
      partialize: (state) => ({
        sources: state.sources,
        recentSearches: state.recentSearches,
        expandedCategories: state.expandedCategories,
      }),
    }
  )
);

// Helper function to search a specific source
async function searchSource(
  source: SearchSource,
  query: string
): Promise<SearchResult[]> {
  const baseUrl = getApiUrl();

  // Route to appropriate search handler
  switch (source.id) {
    case 'google':
    case 'brave':
    case 'duckduckgo':
    case 'wikipedia':
      // Web search API
      const webResponse = await authFetch(`${baseUrl}/api/search/web`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          engine: source.id,
        }),
      });
      if (!webResponse.ok) {
        throw new Error(`Web search failed: ${webResponse.status}`);
      }
      const webData = await webResponse.json();
      return (webData.results || []).map((r: Record<string, unknown>) => ({
        ...r,
        sourceId: source.id,
      }));

    case 'conversations':
    case 'files':
    case 'knowledge-graph':
    case 'ontology':
      // Private search API
      const privateResponse = await authFetch(`${baseUrl}/api/search/private`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          source: source.id,
        }),
      });
      if (!privateResponse.ok) {
        throw new Error(`Private search failed: ${privateResponse.status}`);
      }
      const privateData = await privateResponse.json();
      return (privateData.results || []).map((r: Record<string, unknown>) => ({
        ...r,
        sourceId: source.id,
      }));

    default:
      // Custom source - use generic endpoint
      if (source.apiEndpoint) {
        const customResponse = await fetch(source.apiEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query }),
        });
        if (!customResponse.ok) {
          throw new Error(`Custom search failed: ${customResponse.status}`);
        }
        const customData = await customResponse.json();
        return (customData.results || []).map((r: Record<string, unknown>) => ({
          ...r,
          sourceId: source.id,
        }));
      }
      return [];
  }
}

// Selector helpers
export const selectPublicSources = (state: SearchState) =>
  state.sources.filter((s) => s.category === 'public');

export const selectPrivateSources = (state: SearchState) =>
  state.sources.filter((s) => s.category === 'private');

export const selectCustomSources = (state: SearchState) =>
  state.sources.filter((s) => s.category === 'custom');

export const selectEnabledSources = (state: SearchState) =>
  state.sources.filter((s) => s.enabled);
