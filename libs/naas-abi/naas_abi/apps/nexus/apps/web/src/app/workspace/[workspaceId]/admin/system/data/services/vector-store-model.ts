/** Pure helpers for the vector store view (no React). */

/** ``attributes.sample`` ("0.1,0.2,...") as numbers; empty when absent or bad. */
export function parseSample(raw: string | undefined): number[] {
  if (!raw) return [];
  const values = raw.split(',').map((v) => Number(v));
  return values.every((v) => Number.isFinite(v)) ? values : [];
}

const TEXT_FIELDS = [
  'title',
  'name',
  'text',
  'content',
  'page_content',
  'chunk',
  'document',
  'description',
  'label',
  'source',
];

/** The field a vector most likely embeds (``{field, text}``), from payload then metadata. */
export function textExcerpt(payload: unknown, metadata: unknown): { field: string; text: string } | null {
  for (const field of TEXT_FIELDS) {
    for (const source of [payload, metadata]) {
      if (!source || typeof source !== 'object' || Array.isArray(source)) continue;
      const value = (source as Record<string, unknown>)[field];
      if (typeof value === 'string' && value.trim()) return { field, text: value.trim() };
    }
  }
  return null;
}

const FIELDS = new Set(['vector', 'metadata', 'payload', 'distance_metric']);
const METRICS = ['cosine', 'euclidean', 'l2', 'dot', 'l1'];

/** An error to show, or ``null`` when ``text`` is a writable vector document. */
export function validateVectorDocument(text: string): string | null {
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch (error) {
    return `Not valid JSON: ${error instanceof Error ? error.message : String(error)}`;
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return 'A vector is a JSON object: {"vector": [...], "metadata": {...}, "payload": {...}}.';
  }
  const value = body as Record<string, unknown>;
  const unknown = Object.keys(value).filter((k) => !FIELDS.has(k));
  if (unknown.length) return `Unknown fields: ${unknown.join(', ')}. Use vector, metadata, payload, distance_metric.`;
  if ('vector' in value) {
    const vector = value.vector;
    if (!Array.isArray(vector) || vector.length === 0) return '"vector" must be a non-empty list of numbers.';
    const bad = vector.findIndex((v) => typeof v !== 'number' || !Number.isFinite(v));
    if (bad >= 0) return `"vector" item ${bad} is not a number.`;
  }
  for (const key of ['metadata', 'payload']) {
    const v = value[key];
    if (v !== undefined && v !== null && (typeof v !== 'object' || Array.isArray(v))) {
      return `"${key}" must be a JSON object.`;
    }
  }
  if (value.distance_metric !== undefined && !METRICS.includes(String(value.distance_metric))) {
    return `"distance_metric" must be one of ${METRICS.join(', ')}.`;
  }
  return null;
}

export const VECTOR_TEMPLATE =
  '{\n  "vector": [],\n  "metadata": {},\n  "payload": {\n    "text": ""\n  }\n}\n';
