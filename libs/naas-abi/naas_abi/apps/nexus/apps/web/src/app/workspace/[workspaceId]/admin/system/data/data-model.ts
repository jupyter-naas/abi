/** Pure helpers for the data explorer (no React, no fetch). */
import type { ResourceEntry } from './data-types';

export interface Crumb {
  id: string;
  label: string;
}

export const ROOT_CRUMB: Crumb = { id: '', label: 'All' };

/**
 * The path after opening ``next`` from where ``path`` ends. Ids are opaque (a graph
 * IRI, ``owner/repo/dir``), so crumbs record the containers opened rather than
 * splitting ids; opening a crumb already on the path cuts back to it.
 */
export function openOnPath(path: Crumb[], next: Crumb): Crumb[] {
  const at = path.findIndex((c) => c.id === next.id);
  if (at >= 0) return path.slice(0, at + 1);
  return [...path, next];
}

export function childId(parent: string, name: string): string {
  const clean = name.trim().replace(/^\/+/, '');
  return parent ? `${parent}/${clean}` : clean;
}

/** Destructive changes go through only when the id is typed back exactly. */
export function confirmed(typed: string, id: string): boolean {
  return id !== '' && typed === id;
}

/** Next page appended, without duplicates if the listing moved underneath. */
export function appendPage(current: ResourceEntry[], next: ResourceEntry[]): ResourceEntry[] {
  const seen = new Set(current.map((e) => e.id));
  return [...current, ...next.filter((e) => !seen.has(e.id))];
}

/** Case-insensitive match on name, id and summary (client-side search). */
export function filterEntries(entries: ResourceEntry[], text: string): ResourceEntry[] {
  const needle = text.trim().toLowerCase();
  if (!needle) return entries;
  return entries.filter(
    (e) =>
      e.name.toLowerCase().includes(needle) ||
      e.id.toLowerCase().includes(needle) ||
      (e.attributes.summary ?? '').toLowerCase().includes(needle),
  );
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}

export function plural(count: number, one: string, many: string): string {
  return `${formatCount(count)} ${count === 1 ? one : many}`;
}

/** "just now", "5 min ago", "in 3 h", "yesterday", then a short date. */
export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return '';
  const at = Date.parse(iso);
  if (Number.isNaN(at)) return iso;
  const seconds = Math.round((at - now) / 1000);
  const abs = Math.abs(seconds);
  const future = seconds > 0;
  const say = (value: number, unit: string) => (future ? `in ${value} ${unit}` : `${value} ${unit} ago`);
  if (abs < 45) return future ? 'in a moment' : 'just now';
  if (abs < 3600) return say(Math.round(abs / 60), 'min');
  if (abs < 86_400) return say(Math.round(abs / 3600), 'h');
  if (!future && abs < 2 * 86_400) return 'yesterday';
  if (abs < 7 * 86_400) return say(Math.round(abs / 86_400), 'd');
  const date = new Date(at);
  const sameYear = date.getFullYear() === new Date(now).getFullYear();
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  });
}

export function absoluteTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const at = Date.parse(iso);
  if (Number.isNaN(at)) return iso;
  return new Date(at).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Seconds as "45 s", "12 min", "3 h 5 min", "2 d". */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86_400) {
    const h = Math.floor(seconds / 3600);
    const m = Math.round((seconds % 3600) / 60);
    return m ? `${h} h ${m} min` : `${h} h`;
  }
  return `${Math.round(seconds / 86_400)} d`;
}

/** The parsed value when ``text`` is a JSON object or array, else ``undefined``. */
export function parseJson(text: string | null | undefined): unknown {
  if (!text) return undefined;
  const trimmed = text.trim();
  if (!(trimmed.startsWith('{') || trimmed.startsWith('['))) return undefined;
  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
}

const LANGUAGES: Record<string, string> = {
  json: 'json',
  jsonl: 'json',
  ttl: 'turtle',
  turtle: 'turtle',
  nt: 'turtle',
  csv: 'plaintext',
  tsv: 'plaintext',
  md: 'markdown',
  markdown: 'markdown',
  yaml: 'yaml',
  yml: 'yaml',
  py: 'python',
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  html: 'html',
  htm: 'html',
  css: 'css',
  xml: 'xml',
  svg: 'xml',
  sql: 'sql',
  sh: 'shell',
  bash: 'shell',
  toml: 'ini',
  ini: 'ini',
  go: 'go',
  rs: 'rust',
  java: 'java',
  dockerfile: 'dockerfile',
};

/** A Monaco language id from a file name, a media type or the text itself. */
export function detectLanguage(name: string, mediaType?: string, text?: string | null): string {
  const lower = name.toLowerCase();
  const base = lower.split('/').pop() ?? lower;
  if (base === 'dockerfile') return 'dockerfile';
  const ext = base.includes('.') ? base.split('.').pop() ?? '' : '';
  if (ext && LANGUAGES[ext]) return LANGUAGES[ext];
  if (mediaType) {
    if (mediaType.includes('json')) return 'json';
    if (mediaType.includes('html')) return 'html';
    if (mediaType.includes('xml')) return 'xml';
    if (mediaType.includes('yaml')) return 'yaml';
    if (mediaType.includes('markdown')) return 'markdown';
  }
  if (parseJson(text) !== undefined) return 'json';
  return 'plaintext';
}

export function isImage(name: string, mediaType?: string): boolean {
  if (mediaType?.startsWith('image/')) return true;
  return /\.(png|jpe?g|gif|webp|svg|avif|bmp|ico)$/i.test(name);
}

const WELL_KNOWN_PREFIXES: Record<string, string> = {
  rdf: 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
  rdfs: 'http://www.w3.org/2000/01/rdf-schema#',
  owl: 'http://www.w3.org/2002/07/owl#',
  xsd: 'http://www.w3.org/2001/XMLSchema#',
  skos: 'http://www.w3.org/2004/02/skos/core#',
  dcterms: 'http://purl.org/dc/terms/',
  foaf: 'http://xmlns.com/foaf/0.1/',
  bfo: 'http://purl.obolibrary.org/obo/BFO_',
  cco: 'https://www.commoncoreontologies.org/',
  abi: 'http://ontology.naas.ai/abi/',
};

/** ``prefix:local`` for an IRI when a prefix matches, else the IRI unchanged. */
export function compactIri(iri: string, prefixes: Record<string, string> = {}): string {
  const all = { ...WELL_KNOWN_PREFIXES, ...prefixes };
  let best: [string, string] | null = null;
  for (const [prefix, namespace] of Object.entries(all)) {
    if (namespace && iri.startsWith(namespace) && (!best || namespace.length > best[1].length)) {
      best = [prefix, namespace];
    }
  }
  return best ? `${best[0]}:${iri.slice(best[1].length)}` : iri;
}

/** The last meaningful segment of an IRI or path, for compact labels. */
export function tail(value: string): string {
  const trimmed = value.replace(/[/#]+$/, '');
  const cut = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('#'), trimmed.lastIndexOf(':'));
  return cut >= 0 && cut < trimmed.length - 1 ? trimmed.slice(cut + 1) : trimmed;
}

export function initials(name: string): string {
  const parts = name.replace(/[@._-]+/g, ' ').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase();
}

/** Where the explorer is, as query parameters (deep links survive a refresh). */
export interface Location {
  service: string | null;
  path: Crumb[];
  item: string | null;
}

export function encodeLocation(location: Location, params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params.toString());
  for (const key of ['service', 'in', 'item']) next.delete(key);
  if (location.service) next.set('service', location.service);
  const inner = location.path.slice(1);
  if (inner.length) next.set('in', JSON.stringify(inner.map((c) => [c.id, c.label])));
  if (location.item) next.set('item', location.item);
  return next;
}

export function decodeLocation(params: URLSearchParams): Location {
  let path: Crumb[] = [ROOT_CRUMB];
  const raw = params.get('in');
  if (raw) {
    try {
      const pairs = JSON.parse(raw) as unknown;
      if (Array.isArray(pairs)) {
        path = [
          ROOT_CRUMB,
          ...pairs
            .filter((p): p is [string, string] => Array.isArray(p) && typeof p[0] === 'string')
            .map(([id, label]) => ({ id, label: typeof label === 'string' ? label : tail(id) })),
        ];
      }
    } catch {
      path = [ROOT_CRUMB];
    }
  }
  return { service: params.get('service'), path, item: params.get('item') };
}

/** "Today", "Yesterday", or a short date: day separators in log lists. */
export function dayLabel(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return 'Unknown time';
  const at = new Date(Date.parse(iso));
  if (Number.isNaN(at.getTime())) return 'Unknown time';
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((day(new Date(now)) - day(at)) / 86_400_000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  return at.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    ...(at.getFullYear() === new Date(now).getFullYear() ? {} : { year: 'numeric' }),
  });
}
