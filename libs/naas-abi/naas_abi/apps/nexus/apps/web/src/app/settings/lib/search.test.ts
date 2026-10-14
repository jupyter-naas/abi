import { describe, expect, it } from 'vitest';
import { matchesSearch } from './search';

describe('matchesSearch', () => {
  const texts = ['Map feed layers', 'maps_feed_layers', 'Maps', 'Layers of each map feed.'];

  it('matches everything on an empty query', () => {
    expect(matchesSearch(texts, '')).toBe(true);
    expect(matchesSearch(texts, '   ')).toBe(true);
  });

  it('needs every word, in any text, ignoring case', () => {
    expect(matchesSearch(texts, 'MAPS layer')).toBe(true);
    expect(matchesSearch(texts, 'feed_layers')).toBe(true);
    expect(matchesSearch(texts, 'maps token')).toBe(false);
  });
});
