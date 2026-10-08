/** Pure helpers for the document view (no React). */
import type { ResourceEntry } from '../data-types';

export type DocumentLevel = 'namespace' | 'collection' | 'document';

/** Ids are ``ns/collection/doc`` with the first two segments percent-quoted. */
export function documentLevel(id: string): DocumentLevel {
  const segments = id.split('/').length;
  if (segments <= 1) return 'namespace';
  if (segments === 2) return 'collection';
  return 'document';
}

/** ``operations.projects.nats_probe.researcher`` → lead ``researcher``, context the rest. */
export function namespaceLabel(namespace: string): { lead: string; context: string } {
  const at = namespace.lastIndexOf('.');
  if (at <= 0 || at === namespace.length - 1) return { lead: namespace, context: '' };
  return { lead: namespace.slice(at + 1), context: namespace.slice(0, at) };
}

/** Where a namespace comes from, judged by its module path. */
export function namespaceKind(namespace: string): string {
  if (namespace.startsWith('naas_abi_core')) return 'Core';
  if (namespace === 'naas_abi' || namespace.startsWith('naas_abi.')) return 'Platform';
  if (namespace.startsWith('naas_abi_marketplace')) return 'Marketplace';
  if (namespace.startsWith('operations.projects.')) return 'Project';
  const [first] = namespace.split('.');
  return first ? first.replace(/^\w/, (c) => c.toUpperCase()) : 'Module';
}

const PURPOSES: [RegExp, string][] = [
  [/^agent_runs(_|$)/, 'Agent runs'],
  [/^agent_events(_|$)/, 'Agent events'],
  [/^agent_claims(_|$)/, 'Agent claims'],
  [/^job_runs(_|$)/, 'Job runs'],
  [/^langgraph_checkpoints/, 'LangGraph checkpoints'],
  [/^langgraph_writes/, 'LangGraph writes'],
  [/^langgraph_(blobs|items|parts)/, 'LangGraph values'],
];

/** Document checkpointer collections, any schema version (``_v1`` full snapshots,
 * ``_v2`` increments whose values live in the blobs / items / parts collections). */
const CHECKPOINTS = /^langgraph_checkpoints_v\d+$/;
const WRITES = /^langgraph_writes_v\d+$/;

/** The collection an id sits in (a collection's own name for a collection id), decoded. */
export function collectionOf(id: string): string | null {
  const parts = id.split('/');
  return parts.length > 1 ? decodeURIComponent(parts[1]) : null;
}

/** ``checkpoint`` / ``write`` for LangGraph saver documents and collections, else ``null``. */
export function checkpointKind(id: string): 'checkpoint' | 'write' | null {
  const collection = collectionOf(id);
  if (collection === null) return null;
  return CHECKPOINTS.test(collection) ? 'checkpoint' : WRITES.test(collection) ? 'write' : null;
}

/** The group a checkpoint row belongs to: its thread (ids are often long hashes) and agent. */
export function threadLabel(entry: ResourceEntry): string {
  const thread = entry.attributes.thread ?? '';
  const short = thread.length > 18 ? `${thread.slice(0, 12)}…` : thread || 'no thread';
  return entry.attributes.agent ? `Thread ${short} · ${entry.attributes.agent}` : `Thread ${short}`;
}

/** "Step 3 · loop", or ``null`` when the API sent no step. */
export function checkpointTitle(entry: ResourceEntry): string | null {
  if (checkpointKind(entry.id) === 'write') return entry.attributes.channel ? `Write to ${entry.attributes.channel}` : null;
  const step = entry.attributes.step;
  if (step === undefined) return null;
  return entry.attributes.source ? `Step ${step} · ${entry.attributes.source}` : `Step ${step}`;
}

/** What a well-known collection holds (SDK agents, jobs, checkpoints), or ``null``. */
export function collectionPurpose(name: string): string | null {
  for (const [pattern, label] of PURPOSES) if (pattern.test(name)) return label;
  return null;
}

export type FieldValue = string | number | boolean | null;

/** A document entry's top-level values (``attributes.fields``), or ``{}``. */
export function documentFields(entry: ResourceEntry): Record<string, FieldValue> {
  const raw = entry.attributes.fields;
  if (!raw) return {};
  try {
    const value = JSON.parse(raw) as unknown;
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, FieldValue>) : {};
  } catch {
    return {};
  }
}

const PREFERRED = ['title', 'name', 'label', 'status', 'state', 'type', 'kind', 'email', 'agent', 'module', 'thread_id'];

/**
 * Up to ``max`` keys worth a column: present in at least half the documents
 * (and in two or more), the telling ones (names, states) first.
 */
export function deriveColumnKeys(entries: ResourceEntry[], max = 3): string[] {
  const docs = entries.filter((e) => e.kind === 'item').map(documentFields);
  if (docs.length < 2) return [];
  const counts = new Map<string, number>();
  for (const fields of docs) {
    for (const [key, value] of Object.entries(fields)) {
      if (value !== null && value !== '') counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  const common = [...counts.entries()].filter(([, n]) => n >= Math.max(2, docs.length / 2));
  const rank = (key: string) => {
    const at = PREFERRED.indexOf(key.toLowerCase());
    return at >= 0 ? at : PREFERRED.length;
  };
  return common
    .sort((a, b) => rank(a[0]) - rank(b[0]) || b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, max)
    .map(([key]) => key);
}

/** An error to show, or ``null`` when ``text`` can be saved as a document. */
export function validateDocument(text: string): string | null {
  if (!text.trim()) return 'A document is a JSON object, e.g. {"name": "…"}.';
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (error) {
    return `Not valid JSON: ${error instanceof Error ? error.message : String(error)}`;
  }
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return 'A document must be a JSON object ({…}), not an array or a single value.';
  }
  const tag = (value as Record<string, unknown>).$t;
  if (tag !== undefined && Object.keys(value as object).length === 2 && '$v' in (value as object)) {
    return 'The top level cannot be a tagged value; wrap it in an object.';
  }
  return null;
}

export function validateDocumentId(name: string): string | null {
  if (name !== name.trim()) return 'No leading or trailing spaces.';
  if (name.includes('\u0000')) return 'An id cannot contain NUL characters.';
  return null;
}

export const DOCUMENT_TEMPLATE = '{\n  "name": "",\n  "status": "draft"\n}\n';

/** A collection's declared fields and unique groups (``spec`` attribute). */
export interface CollectionSpecView {
  fields: { name: string; type: string; indexed: boolean; unique: boolean }[];
  unique_together: string[][];
}

export function collectionSpec(entry: { attributes: Record<string, string> }): CollectionSpecView | null {
  try {
    const value = JSON.parse(entry.attributes.spec ?? '') as CollectionSpecView;
    return Array.isArray(value.fields) ? { fields: value.fields, unique_together: value.unique_together ?? [] } : null;
  } catch {
    return null;
  }
}

/** One line per declared field ("email: string, unique") and unique group. */
export function describeSpec(spec: CollectionSpecView): string[] {
  const lines = spec.fields.map((f) => {
    const traits = [f.unique ? 'unique' : '', f.indexed ? 'indexed' : ''].filter(Boolean);
    return `${f.name}: ${f.type}${traits.length ? `, ${traits.join(', ')}` : ''}`;
  });
  return [...lines, ...spec.unique_together.map((group) => `unique together: ${group.join(' + ')}`)];
}
