import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { slidesFilmstripEmptyCopy } from './slides-section-views';

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'slides-section.tsx'),
  'utf8',
);

describe('SlidesSection sidebar views', () => {
  it('copies the Ontology toolbar: Decks and Filmstrip under the title', () => {
    expect(src).toContain('SidebarToolbar');
    expect(src).toContain('SidebarToolbarButton');
    expect(src).toContain('label="Decks"');
    expect(src).toContain('label="Filmstrip"');
    expect(src).toContain('data-testid="slides-sidebar-views"');
    expect(src).toContain('slides-sidebar-view-filmstrip');
    expect(src).toContain('SlidesFilmstrip');
  });

  it('applies a rename title from the deck-updated event before refetch', () => {
    expect(src).toContain('SLIDES_DECK_UPDATED_EVENT');
    expect(src).toContain('detail?.title');
    expect(src).toContain('setSelectedTitle(title)');
  });

  it('does not treat a leftover selected slug as a loading filmstrip', () => {
    expect(slidesFilmstripEmptyCopy(false)).toBe('Open a deck to see slides.');
    expect(slidesFilmstripEmptyCopy(true)).toBe('Loading slides…');
  });
});
