/**
 * Search scopes — everything the search page can look into.
 *
 * Three kinds, one shape:
 * - `feature`: a Nexus feature (Apps, Chat, Files, Ontology…), searched by a
 *   client provider over that feature's own API (`search-providers.ts`);
 * - `topic`:   a SPARQL search topic (People, Organizations…, `search-topics.ts`);
 * - `web`:     the external engines and private sources of the legacy search.
 *
 * Every scope can be switched on or off for the "All" view (sidebar toggles),
 * and opened on its own (`?scope=<id>`). Pure: no store, no fetch.
 */
import type { FeatureKey } from '@/lib/feature-access';
import type { SearchTopic } from '@/lib/search-topics';

export type ScopeKind = 'feature' | 'topic' | 'web';

export interface SearchScope {
  id: string;
  kind: ScopeKind;
  label: string;
  /** Lucide icon name (see `components/search/topic-icon.tsx`). */
  icon: string;
  description: string;
  /** Workspace feature flag that must be on for the scope to exist. */
  feature?: FeatureKey;
  /** Off by default in the "All" view (e.g. Web sends the query to third parties). */
  offByDefault?: boolean;
}

export type ScopeHitAction =
  | { kind: 'href'; href: string }
  | { kind: 'external'; href: string }
  | { kind: 'file'; source: string; path: string; type: 'file' | 'folder' }
  /** A topic individual: opens the topic's detail on the search page. */
  | { kind: 'topic-item'; topic: string; uri: string };

export interface ScopeHit {
  id: string;
  title: string;
  subtitle?: string | null;
  snippet?: string | null;
  image?: string | null;
  action: ScopeHitAction | null;
}

export interface ScopeResult {
  hits: ScopeHit[];
  hasMore: boolean;
  /** Every match when the scope can count them (topics), not only the hits returned. */
  total?: number;
  /** Caveat shown under the group, e.g. what the provider does not cover yet. */
  note?: string;
}

/** The exact count when the scope gives one, else what came back ("5+" when there is more). */
export function formatHitCount(result: Pick<ScopeResult, 'hits' | 'hasMore' | 'total'>): string {
  if (typeof result.total === 'number') return String(result.total);
  return `${result.hits.length}${result.hasMore ? '+' : ''}`;
}

export const ALL_SCOPE = 'all';
export const WEB_SCOPE = 'web';

/** Nexus features the search can read, in sidebar order. */
export const FEATURE_SCOPES: readonly SearchScope[] = [
  { id: 'apps', kind: 'feature', feature: 'apps', label: 'Apps', icon: 'AppWindow', description: 'Apps in the workspace catalog' },
  { id: 'chat', kind: 'feature', feature: 'chat', label: 'Chats', icon: 'MessageSquare', description: 'Conversation titles' },
  { id: 'files', kind: 'feature', feature: 'files', label: 'Files', icon: 'Folder', description: 'File names in the workspace drive' },
  { id: 'documents', kind: 'feature', feature: 'documents', label: 'Documents', icon: 'FileText', description: 'Document titles' },
  { id: 'slides', kind: 'feature', feature: 'slides', label: 'Slides', icon: 'Presentation', description: 'Presentation titles' },
  { id: 'sheets', kind: 'feature', feature: 'sheets', label: 'Sheets', icon: 'Sheet', description: 'Workbook titles' },
  { id: 'datasets', kind: 'feature', feature: 'datasets', label: 'Datasets', icon: 'Database', description: 'Dataset names and columns' },
  { id: 'ontology', kind: 'feature', feature: 'ontology', label: 'Ontology', icon: 'BookOpen', description: 'Classes, properties and individuals of the workspace ontologies' },
  { id: 'graph', kind: 'feature', feature: 'graph', label: 'Knowledge graph', icon: 'Network', description: 'Labels and definitions in the graphs this workspace can read' },
  { id: 'maps', kind: 'feature', feature: 'maps', label: 'Maps', icon: 'MapPin', description: 'Map layers' },
  { id: 'agents', kind: 'feature', feature: 'agents', label: 'Agents', icon: 'Bot', description: 'Agents available in the workspace' },
];

/** Engines `/api/search/web` implements. Each can be switched off per workspace as "web.<id>". */
export const WEB_ENGINES: readonly { id: string; label: string; icon: string; description: string }[] = [
  { id: 'wikipedia', label: 'Wikipedia', icon: 'BookOpen', description: 'Wikipedia articles (free API)' },
  { id: 'duckduckgo', label: 'DuckDuckGo', icon: 'Search', description: 'DuckDuckGo instant answers (free API)' },
];
export const WEB_ENGINE_IDS: readonly string[] = WEB_ENGINES.map(e => e.id);
export const webEngineScopeId = (engineId: string) => `web.${engineId}`;

/** Engines the workspace has not switched off. */
export function allowedWebEngines(disabled: readonly string[]): string[] {
  return WEB_ENGINE_IDS.filter(id => !disabled.includes(webEngineScopeId(id)));
}

export const WEB_SCOPE_DEF: SearchScope = {
  id: WEB_SCOPE, kind: 'web', label: 'Web', icon: 'Globe', offByDefault: true,
  description: 'Web engines and private sources — the query leaves Nexus',
};

/** Ids a custom topic may not take: they name features or views of the page. */
export const RESERVED_SCOPE_IDS: readonly string[] = [ALL_SCOPE, WEB_SCOPE, ...FEATURE_SCOPES.map(s => s.id)];

export function topicScope(topic: SearchTopic): SearchScope {
  return { id: topic.id, kind: 'topic', label: topic.plural_label, icon: topic.icon, description: topic.description };
}

/**
 * Every scope available here: enabled topics, the features the workspace has
 * and has not switched off in Settings → Search, then Web while one of its
 * engines is still allowed.
 */
export function availableScopes(
  topics: SearchTopic[],
  featureOn: (feature: FeatureKey) => boolean,
  disabled: readonly string[] = [],
): SearchScope[] {
  return [
    ...topics.filter(t => t.enabled).map(topicScope),
    ...FEATURE_SCOPES.filter(s => (!s.feature || featureOn(s.feature)) && !disabled.includes(s.id)),
    ...(allowedWebEngines(disabled).length ? [WEB_SCOPE_DEF] : []),
  ];
}

/** Toggles store only what differs from the default, so a new topic starts on. */
export function isScopeOn(scope: SearchScope, overrides: Record<string, boolean>): boolean {
  return overrides[scope.id] ?? !scope.offByDefault;
}

export function scopeGroups(scopes: SearchScope[]): { id: ScopeKind; label: string; scopes: SearchScope[] }[] {
  const groups: { id: ScopeKind; label: string }[] = [
    { id: 'topic', label: 'Custom' },
    { id: 'feature', label: 'Workspace' },
    { id: 'web', label: 'Web' },
  ];
  return groups.map(g => ({ ...g, scopes: scopes.filter(s => s.kind === g.id) })).filter(g => g.scopes.length > 0);
}

// -- matching ------------------------------------------------------------------

export function fold(value: string): string {
  return value.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

/** 3 exact, 2 prefix, 1 contained (title or any other field), 0 no match. Every word must match. */
export function matchScore(query: string, title: string, ...fields: (string | null | undefined)[]): number {
  const q = fold(query);
  if (!q) return 1;
  const t = fold(title);
  const rest = fields.filter(Boolean).map(f => fold(f!)).join(' \u0000 ');
  const words = q.split(/\s+/);
  if (!words.every(w => t.includes(w) || rest.includes(w))) return 0;
  if (t === q) return 3;
  if (t.startsWith(q)) return 2;
  return 1;
}

/** Rank items by `matchScore`, then title; keep `limit`, report whether more matched. */
export function rankItems<T>(
  items: readonly T[],
  query: string,
  fields: (item: T) => [string, ...(string | null | undefined)[]],
  limit: number,
): { items: T[]; hasMore: boolean } {
  const scored = items
    .map(item => { const [title, ...rest] = fields(item); return { item, title, score: matchScore(query, title, ...rest) }; })
    .filter(entry => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.title.localeCompare(b.title));
  return { items: scored.slice(0, limit).map(e => e.item), hasMore: scored.length > limit };
}
