/**
 * Search topics — the client half of `services/search/topics` (API).
 *
 * A topic (Person, Organization, …) is a set of SPARQL templates whose
 * projected variables fill fixed slots: a results list, a detail header and
 * detail sections. The search page renders every topic with the same
 * components, so a new topic is a settings entry, never new UI.
 */
export type QueryRole = 'results' | 'header' | 'section' | 'image' | 'row';
export type TopicSource = 'builtin' | 'override' | 'custom';

export interface TopicSection {
  id: string;
  label: string;
  query: string;
  empty_text: string;
  link_topic: string | null;
}

/** One labelled line of metadata under each result, filled by a `row` query. */
export interface TopicResultRowDef {
  id: string;
  label: string;
  query: string;
}

export interface SearchTopic {
  id: string;
  label: string;
  plural_label: string;
  description: string;
  icon: string;
  class_iri: string;
  results_query: string;
  header_query: string;
  sections: TopicSection[];
  /** The picture of each result (`image` role, `VALUES ?uri { {{ uris }} }`). Empty: the results query's ?image. */
  image_query: string;
  /** Metadata lines under each result (`row` role), in order. */
  result_rows: TopicResultRowDef[];
  /** The tab that shows one individual: "Profile" for a person, "Card" for an organization. */
  detail_label: string;
  /** Graphs read, within the workspace's. Empty: every graph the workspace can read. */
  graphs: string[];
  enabled: boolean;
  order: number;
  source: TopicSource;
}

export interface TopicResultItem {
  uri: string;
  title: string;
  subtitle: string | null;
  snippet: string | null;
  image: string | null;
  score: number | null;
  rows: { id: string; label: string; value: string }[];
}

export interface TopicResults {
  topic_id: string;
  query: string;
  items: TopicResultItem[];
  has_more: boolean;
  sparql: string;
}

export interface TopicFact { key: string; label: string; value: string; is_uri: boolean }

export interface TopicSectionItem {
  title: string;
  item: string | null;
  subtitle: string | null;
  snippet: string | null;
  image: string | null;
  start: string | null;
  end: string | null;
  url: string | null;
  /** Labels shown as chips on the row (the skills and languages an experience developed). */
  tags?: string[];
}

export interface TopicSectionResult {
  id: string;
  label: string;
  empty_text: string;
  link_topic: string | null;
  items: TopicSectionItem[];
  sparql: string;
  error: string | null;
}

export interface TopicDetail {
  topic_id: string;
  uri: string;
  title: string;
  subtitle: string | null;
  snippet: string | null;
  image: string | null;
  url: string | null;
  facts: TopicFact[];
  sections: TopicSectionResult[];
  header_sparql: string;
}

export interface RoleContract {
  placeholders: string[];
  required: string[];
  optional: string[];
  extra_as_facts: boolean;
}

export interface PreviewBinding { value: string; is_uri: boolean }
export interface PreviewResult { sparql: string; rows: Record<string, PreviewBinding>[] }

export type SearchTab = 'results' | 'ontology' | 'details';

// -- URL state ---------------------------------------------------------------
// /search?scope=person&q=alice&item=<iri>&tab=details — every view is a link.
// No scope is the "All" view. `?topic=` is the earlier name of `?scope=`.

export interface SearchRoute { scope: string | null; q: string; item: string | null; tab: SearchTab }

export function readSearchRoute(params: Pick<URLSearchParams, 'get'> | null): SearchRoute {
  const tab = params?.get('tab');
  return {
    scope: params?.get('scope') || params?.get('topic') || null,
    q: params?.get('q') || '',
    item: params?.get('item') || null,
    tab: tab === 'ontology' || tab === 'details' ? tab : 'results',
  };
}

export function searchHref(workspaceId: string, route: Partial<SearchRoute>): string {
  const params = new URLSearchParams();
  if (route.scope && route.scope !== 'all') params.set('scope', route.scope);
  if (route.q) params.set('q', route.q);
  if (route.item) params.set('item', route.item);
  if (route.tab && route.tab !== 'results') params.set('tab', route.tab);
  const query = params.toString();
  return `/workspace/${encodeURIComponent(workspaceId)}/search${query ? `?${query}` : ''}`;
}

/** The requested scope when it exists here, otherwise the "All" view (null). */
export function resolveScope(available: readonly { id: string }[], requested: string | null): string | null {
  return requested && available.some(s => s.id === requested) ? requested : null;
}

/**
 * Images are rendered only from addresses the browser can load safely. A graph
 * path under `/api/` names a route of the ABI API, which Nexus does not serve
 * on its own origin: it is resolved against `apiBase` when one is given.
 */
export function safeImage(src: string | null | undefined, apiBase?: string): string | null {
  if (!src) return null;
  if (apiBase && src.startsWith('/api/')) return apiBase.replace(/\/+$/, '') + src;
  return /^(https?:\/\/|\/)/i.test(src) || /^data:image\/(png|jpe?g|gif|webp|svg\+xml);/i.test(src) ? src : null;
}

export function initials(label: string): string {
  return label.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]!.toUpperCase()).join('') || '?';
}

/** "2019-10-01" → "Oct 2019"; open-ended periods read "– present". */
export function formatPeriod(start: string | null, end: string | null): string | null {
  const fmt = (value: string) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString('en', { month: 'short', year: 'numeric', timeZone: 'UTC' });
  };
  if (!start && !end) return null;
  if (!start) return `until ${fmt(end!)}`;
  return `${fmt(start)} – ${end ? fmt(end) : 'present'}`;
}

/** A blank custom topic that already fits the contract, for the settings editor. */
export function blankTopic(id: string): SearchTopic {
  return {
    id,
    label: 'New topic',
    plural_label: 'New topics',
    description: '',
    icon: 'Search',
    class_iri: '',
    enabled: true,
    order: 100,
    source: 'custom',
    graphs: [],
    image_query: '',
    result_rows: [],
    detail_label: 'Details',
    results_query: `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?uri ?title
WHERE {
  ?uri a <http://example.org/Class> ;
       rdfs:label ?title .
  FILTER(CONTAINS(LCASE(STR(?title)), LCASE("{{ q }}")))
}
ORDER BY LCASE(STR(?title))
LIMIT {{ limit }}
OFFSET {{ offset }}`,
    header_query: `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?title
WHERE {
  {{ uri }} rdfs:label ?title .
}
LIMIT 1`,
    sections: [],
  };
}
