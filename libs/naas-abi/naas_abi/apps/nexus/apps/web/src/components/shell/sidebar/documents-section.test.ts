import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { sectionsFilmstripEmptyCopy } from './documents-section-views';

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'documents-section.tsx'),
  'utf8',
);

describe('DocumentsSection sidebar views', () => {
  it('copies the Ontology toolbar: Documents and Outline under the title', () => {
    expect(src).toContain('SidebarToolbar');
    expect(src).toContain('SidebarToolbarButton');
    expect(src).toContain('label="Documents"');
    expect(src).toContain('label="Outline"');
    expect(src).toContain('data-testid="sections-sidebar-views"');
    expect(src).toContain('sections-sidebar-view-outline');
    expect(src).toContain('DocumentsOutline');
  });

  it('does not treat a leftover selected slug as a loading outline', () => {
    expect(sectionsFilmstripEmptyCopy(false)).toBe('Open a document to see its sections.');
    expect(sectionsFilmstripEmptyCopy(true)).toBe('Loading sections…');
  });
});
