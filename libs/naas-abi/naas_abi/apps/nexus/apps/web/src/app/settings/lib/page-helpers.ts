/**
 * Small helpers the Platform Settings pages share. No React here.
 */
import type { FacetBucket } from '@/lib/graph-query/types';

/** A URL segment decoded, or as it is when it is not valid percent-encoding. */
export function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** The API's `detail` message, or `fallback` when the answer has none. */
export async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
  } catch {
    // ignore parse errors
  }
  return fallback;
}

/** Each distinct value and how often it occurs, sorted by value: a column filter's choices. */
export function countFacets(values: string[]): FacetBucket[] {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}
