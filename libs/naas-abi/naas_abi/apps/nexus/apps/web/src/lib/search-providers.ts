'use client';

/**
 * One provider per search scope (see `search-scopes.ts`). A provider takes the
 * query and returns `ScopeHit`s; it reads the feature's own store or API, so
 * search sees exactly what the feature would show this user.
 *
 * Feature providers filter lists client-side with `rankItems` — enough for
 * workspace-sized lists, and the reason a feature with a large corpus (files)
 * says what it does not cover in `note`. Moving a feature to a server-side
 * index changes its provider only.
 */
import { getApiUrl } from '@/lib/config';
import { termViews } from '@/lib/ontology-navigation';
import { rankItems, type ScopeHit, type ScopeResult, type SearchScope } from '@/lib/search-scopes';
import { topicsApi } from '@/lib/search-topics-api';
import { MAPS_DATASETS } from '@/app/workspace/[workspaceId]/maps/lib/datasets';
import { useAppsStore } from '@/stores/apps';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useSearchStore, WEB_ENGINE_IDS } from '@/stores/search';

export interface ProviderContext { workspaceId: string; limit: number }
type Provider = (q: string, ctx: ProviderContext) => Promise<ScopeResult>;

const ws = (ctx: ProviderContext, path: string) => `/workspace/${encodeURIComponent(ctx.workspaceId)}${path}`;
const href = (value: string): ScopeHit['action'] => ({ kind: 'href', href: value });

// Lists that do not change while someone types: fetched once a minute per workspace.
const LIST_TTL_MS = 60_000;
const listCache = new Map<string, { at: number; value: Promise<unknown> }>();
function cachedList<T>(key: string, load: () => Promise<T>): Promise<T> {
  const hit = listCache.get(key);
  if (hit && Date.now() - hit.at < LIST_TTL_MS) return hit.value as Promise<T>;
  const value = load().catch(error => { listCache.delete(key); throw error; });
  listCache.set(key, { at: Date.now(), value });
  return value;
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authFetch(`${getApiUrl()}${path}`, init);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

function officeProvider(kind: 'documents' | 'slides' | 'sheets'): Provider {
  return async (q, ctx) => {
    const projects = await cachedList(`${kind}:${ctx.workspaceId}`, () =>
      getJson<{ slug: string; title: string; updated_at?: string | null; archived?: boolean }[]>(
        `/api/${kind}/projects?workspace_id=${encodeURIComponent(ctx.workspaceId)}`,
      ));
    const ranked = rankItems(projects.filter(p => !p.archived), q, p => [p.title || p.slug, p.slug], ctx.limit);
    return {
      hasMore: ranked.hasMore,
      hits: ranked.items.map(p => ({
        id: p.slug,
        title: p.title || p.slug,
        subtitle: p.updated_at ? `Updated ${new Date(p.updated_at).toLocaleDateString()}` : null,
        action: href(ws(ctx, `/${kind}/${encodeURIComponent(p.slug)}`)),
      })),
    };
  };
}

const PROVIDERS: Record<string, Provider> = {
  apps: async (q, ctx) => {
    const store = useAppsStore.getState();
    if (store.workspaceId !== ctx.workspaceId || !store.apps.length) await store.fetchApps(ctx.workspaceId);
    // The catalog lists every app with this workspace's enable state: search only the enabled ones.
    const apps = useAppsStore.getState().apps.filter(a => a.enabled);
    const ranked = rankItems(apps, q, a => [a.name, a.description, (a.keywords || []).join(' '), a.category], ctx.limit);
    return {
      hasMore: ranked.hasMore,
      hits: ranked.items.map(a => ({
        id: a.app_id,
        title: `${a.icon_emoji ? `${a.icon_emoji} ` : ''}${a.name}`,
        subtitle: a.category,
        snippet: a.description,
        image: a.avatar_url,
        action: href(ws(ctx, `/apps?open=${encodeURIComponent(a.app_id)}`)),
      })),
    };
  },

  chat: async (q, ctx) => {
    // The API returns only the signed-in user's conversations in this workspace;
    // the browser's conversation store is not a safe source (it may hold others).
    const userId = useAuthStore.getState().user?.id ?? 'anonymous';
    const conversations = await cachedList(`chat:${userId}:${ctx.workspaceId}`, () =>
      getJson<{ id: string; title: string; archived?: boolean; updated_at?: string | null }[]>(
        `/api/chat/conversations?workspace_id=${encodeURIComponent(ctx.workspaceId)}&limit=200`,
      ));
    const ranked = rankItems(conversations.filter(c => !c.archived), q, c => [c.title || 'Untitled chat'], ctx.limit);
    return {
      hasMore: ranked.hasMore,
      hits: ranked.items.map(c => ({
        id: c.id,
        title: c.title || 'Untitled chat',
        subtitle: c.updated_at ? `Updated ${new Date(c.updated_at).toLocaleDateString()}` : null,
        action: href(ws(ctx, `/chat/${encodeURIComponent(c.id)}`)),
      })),
    };
  },

  files: async (q, ctx) => {
    const params = new URLSearchParams({ path: '', workspace_id: ctx.workspaceId, scope: 'workspace', limit: String(ctx.limit + 1) });
    if (q.trim()) params.set('search', q.trim());
    const data = await getJson<{ files: { name: string; path: string; type: string }[] }>(`/api/files/?${params}`);
    const files = data.files.slice(0, ctx.limit);
    return {
      hasMore: data.files.length > ctx.limit,
      note: 'File names in the top folder of the workspace drive.',
      hits: files.map(f => ({
        id: f.path,
        title: f.name,
        subtitle: f.type === 'folder' ? 'Folder' : f.path,
        action: { kind: 'file', source: 'workspace', path: f.path, type: f.type === 'folder' ? 'folder' : 'file' },
      })),
    };
  },

  documents: officeProvider('documents'),
  slides: officeProvider('slides'),
  sheets: officeProvider('sheets'),

  datasets: async (q, ctx) => {
    const { datasets } = await cachedList(`datasets:${ctx.workspaceId}`, () =>
      getJson<{ datasets: { name: string; namespace: string; columns: { name: string }[] }[] }>(
        `/api/datasets/?workspace_id=${encodeURIComponent(ctx.workspaceId)}`,
      ));
    const ranked = rankItems(datasets, q, d => [d.name, d.namespace, d.columns.map(c => c.name).join(' ')], ctx.limit);
    return {
      hasMore: ranked.hasMore,
      hits: ranked.items.map(d => ({
        id: `${d.namespace}.${d.name}`,
        title: d.name,
        subtitle: `${d.namespace} · ${d.columns.length} columns`,
        action: href(ws(ctx, `/datasets/${encodeURIComponent(d.namespace)}/${encodeURIComponent(d.name)}`)),
      })),
    };
  },

  ontology: async (q, ctx) => {
    const store = useOntologyDictionaryStore.getState();
    if (store.workspaceId !== ctx.workspaceId) await store.load(ctx.workspaceId);
    const { terms } = useOntologyDictionaryStore.getState();
    const ranked = rankItems(terms, q, t => [t.name, t.id, (t.definitions || []).map(d => d.value).join(' ')], ctx.limit);
    const kind: Record<string, string> = { entity: 'Class', relationship: 'Object property', attribute: 'Data property', annotation: 'Annotation', individual: 'Individual' };
    return {
      hasMore: ranked.hasMore,
      hits: ranked.items.map(t => ({
        id: `${t.type}:${t.id}`,
        title: t.name,
        subtitle: `${kind[t.type] || t.type} · ${t.id}`,
        snippet: t.definitions?.[0]?.value,
        action: href(ws(ctx, `/ontology?${new URLSearchParams({ browser: 'dictionary', view: termViews[t.type], term: t.id, termType: t.type })}`)),
      })),
    };
  },

  graph: async (q, ctx) => {
    if (!q.trim()) return { hits: [], hasMore: false, note: 'Type to search labels in the workspace graphs.' };
    const data = await getJson<{ results: { id: string; title: string; snippet: string }[] }>('/api/search/private', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, source: 'ontology', workspace_id: ctx.workspaceId }),
    });
    const results = data.results.slice(0, ctx.limit);
    return {
      hasMore: data.results.length > ctx.limit,
      hits: results.map(r => ({ id: r.id, title: r.title, subtitle: r.id, snippet: r.snippet || null, action: null })),
    };
  },

  maps: async (q, ctx) => {
    const ranked = rankItems(MAPS_DATASETS, q, m => [m.title, m.description, m.category], ctx.limit);
    return {
      hasMore: ranked.hasMore,
      hits: ranked.items.map(m => ({
        id: m.id,
        title: m.title,
        subtitle: m.category,
        snippet: m.description,
        action: href(ws(ctx, `/maps/${encodeURIComponent(m.id)}`)),
      })),
    };
  },

  agents: async (q, ctx) => {
    // The workspace's own roster (already filtered by its feature flags), enabled agents only.
    // Not the agents store: it keeps one list across workspaces.
    const agents = await cachedList(`agents:${ctx.workspaceId}`, () =>
      getJson<{ id: string; name: string; description: string; enabled: boolean; logo_url: string | null }[]>(
        `/api/agents/?workspace_id=${encodeURIComponent(ctx.workspaceId)}`,
      ));
    const ranked = rankItems(agents.filter(a => a.enabled), q, a => [a.name, a.description], ctx.limit);
    return {
      hasMore: ranked.hasMore,
      hits: ranked.items.map(a => ({
        id: a.id,
        title: a.name,
        snippet: a.description,
        image: a.logo_url,
        action: href(ws(ctx, `/settings/agents/${encodeURIComponent(a.id)}`)),
      })),
    };
  },
};

async function topicProvider(scope: SearchScope, q: string, ctx: ProviderContext): Promise<ScopeResult> {
  const page = await topicsApi.results(ctx.workspaceId, scope.id, q, 0, ctx.limit);
  return {
    hasMore: page.has_more,
    total: page.total ?? undefined,
    hits: page.items.map(item => ({
      id: item.uri,
      title: item.title,
      // Without a subtitle, the topic's metadata rows say what the result is ("People 746").
      subtitle: item.subtitle || (item.rows || []).map(row => `${row.label} ${row.value}`).join(' · ') || null,
      snippet: item.snippet,
      image: item.image,
      action: { kind: 'topic-item', topic: scope.id, uri: item.uri },
    })),
  };
}

async function webProvider(q: string, ctx: ProviderContext): Promise<ScopeResult> {
  if (!q.trim()) return { hits: [], hasMore: false, note: 'Type to search the web.' };
  const store = useSearchStore.getState();
  if (!store.sources.some(s => s.enabled && (store.allowedEngineIds ?? WEB_ENGINE_IDS).includes(s.id))) {
    return { hits: [], hasMore: false, note: 'No web engine is switched on.' };
  }
  if (store.query !== q) await store.search(q);
  const { results, sources } = useSearchStore.getState();
  const sorted = [...results].sort((a, b) => (b.relevance || 0) - (a.relevance || 0));
  return {
    hasMore: sorted.length > ctx.limit,
    hits: sorted.slice(0, ctx.limit).map(r => ({
      id: `${r.sourceId}:${r.id}`,
      title: r.title,
      subtitle: sources.find(s => s.id === r.sourceId)?.name || r.sourceId,
      snippet: r.snippet,
      image: (r.metadata?.image as string | undefined) || null,
      action: r.url ? { kind: 'external', href: r.url } : null,
    })),
  };
}

export function runScope(scope: SearchScope, q: string, ctx: ProviderContext): Promise<ScopeResult> {
  if (scope.kind === 'topic') return topicProvider(scope, q, ctx);
  if (scope.kind === 'web') return webProvider(q, ctx);
  const provider = PROVIDERS[scope.id];
  if (!provider) return Promise.resolve({ hits: [], hasMore: false, note: 'This feature cannot be searched yet.' });
  return provider(q, ctx);
}
