/**
 * Global search: every word of the query must appear (case-insensitive) in at
 * least one of the texts, so "maps layer" finds "Map feed layers / maps_feed_layers".
 */
export function matchesSearch(texts: readonly string[], query: string): boolean {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const haystack = texts.join(' ').toLowerCase();
  return words.every((word) => haystack.includes(word));
}
