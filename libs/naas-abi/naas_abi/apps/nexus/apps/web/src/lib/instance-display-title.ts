export type InstanceTitleSource = {
  uri?: string;
  label?: string | null;
  properties?: Record<string, string | undefined | null>;
  dataProperties?: Array<{ predicate_uri: string; predicate_label?: string; value: string }>;
};

/** Highest priority first: rdfs:label, skos:prefLabel, then a name property. */
const TITLE_RANK: Array<[RegExp, number]> = [
  [/^label$/, 0],
  [/^(preflabel|preferredlabel)$/, 1],
  [/^(name|displayname)$/, 2],
];

function compactLocalName(value: string): string {
  const tail = value.split(/[#/:]/).filter(Boolean).pop() || value;
  return tail.toLowerCase().replace(/[\s_-]+/g, '');
}

export function uriLocalName(uri: string): string {
  return uri.split(/[#/]/).filter(Boolean).pop() || uri;
}

function titlePredicateRank(uri: string, label = ''): number | null {
  const keys = [compactLocalName(uri), compactLocalName(label)].filter(Boolean);
  for (const [pattern, rank] of TITLE_RANK) {
    if (keys.some(key => pattern.test(key))) return rank;
  }
  return null;
}

function usableTitle(value: string | undefined | null): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed || undefined;
}

function isIriLocalName(value: string, uri?: string): boolean {
  if (!uri) return false;
  return value === uri || value === uriLocalName(uri);
}

/**
 * Page title for an instance. Uses a display label from the triples when
 * present. The API `label` field is only a fallback, and is ignored when it
 * is just the IRI local name.
 */
export function resolveInstanceDisplayTitle(source: InstanceTitleSource): string {
  const candidates: Array<{ value: string; rank: number }> = [];
  const add = (predicate: string, label: string, value: string | undefined | null) => {
    const title = usableTitle(value);
    const rank = titlePredicateRank(predicate, label);
    if (!title || rank == null) return;
    candidates.push({ value: title, rank });
  };

  for (const row of source.dataProperties || []) {
    add(row.predicate_uri, row.predicate_label || '', row.value);
  }
  for (const [key, value] of Object.entries(source.properties || {})) {
    add(key, key, value);
  }

  candidates.sort((a, b) => a.rank - b.rank);
  if (candidates[0]) return candidates[0].value;

  const fallback = usableTitle(source.label);
  if (fallback && !isIriLocalName(fallback, source.uri)) return fallback;
  return source.uri ? uriLocalName(source.uri) : fallback || '';
}
