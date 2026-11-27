import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { startNewWorkbook } from '@/lib/create-sheets-project';
import { DOCUMENTS_SECTION } from './documents-section';
import { officeDetailEmptyCopy } from './office-section';
import { SHEETS_SECTION } from './sheets-section';
import { SLIDES_SECTION } from './slides-section';

const here = dirname(fileURLToPath(import.meta.url));
const read = (file: string) => readFileSync(join(here, file), 'utf8');

describe('OfficeSection', () => {
  const src = read('office-section.tsx');

  it('copies the Ontology toolbar: the tree view and the detail view under the title', () => {
    expect(src).toContain('SidebarToolbar');
    expect(src).toContain('SidebarToolbarButton');
    expect(src).toContain('data-testid={`${prefix}-sidebar-views`}');
    expect(src).toContain('testId={`${prefix}-sidebar-view-${view.id}`}');
  });
});

describe.each([
  {
    config: DOCUMENTS_SECTION,
    file: 'documents-section.tsx',
    tree: 'Documents',
    detail: 'Outline',
    detailId: 'outline',
    detailComponent: 'DocumentsOutline',
    prefix: 'sections',
    empty: ['Open a document to see its sections.', 'Loading sections…'],
  },
  {
    config: SHEETS_SECTION,
    file: 'sheets-section.tsx',
    tree: 'Sheets',
    detail: 'Filmstrip',
    detailId: 'filmstrip',
    detailComponent: 'SheetsFilmstrip',
    prefix: 'sheets',
    empty: ['Open a workbook to see sheet tabs.', 'Loading sheets…'],
  },
  {
    config: SLIDES_SECTION,
    file: 'slides-section.tsx',
    tree: 'Decks',
    detail: 'Filmstrip',
    detailId: 'filmstrip',
    detailComponent: 'SlidesFilmstrip',
    prefix: 'slides',
    empty: ['Open a deck to see slides.', 'Loading slides…'],
  },
])('$tree sidebar views', ({ config, file, tree, detail, detailId, detailComponent, prefix, empty }) => {
  it(`shows ${tree} and ${detail} under the title`, () => {
    expect(config.views.tree.label).toBe(tree);
    expect(config.views.detail.label).toBe(detail);
    expect(config.views.detail.id).toBe(detailId);
    expect(config.kind.testIdPrefix).toBe(prefix);
    expect(read(file)).toContain(detailComponent);
  });

  it('does not treat a leftover selected slug as a loading detail view', () => {
    expect(officeDetailEmptyCopy(config.views.detail, false)).toBe(empty[0]);
    expect(officeDetailEmptyCopy(config.views.detail, true)).toBe(empty[1]);
  });
});

describe('New item', () => {
  it('opens Documents and Slides through the shared create overlay', () => {
    expect(DOCUMENTS_SECTION.create).toEqual({ overlay: 'document' });
    expect(SLIDES_SECTION.create).toEqual({ overlay: 'deck' });
  });

  it('wires New workbook through startNewWorkbook', () => {
    expect(SHEETS_SECTION.newItem.label).toBe('New workbook');
    expect('start' in SHEETS_SECTION.create && SHEETS_SECTION.create.start).toBe(startNewWorkbook);
  });

  it('keeps list recovery on Documents only', () => {
    expect(DOCUMENTS_SECTION.recoverList).toBe(true);
    expect(SHEETS_SECTION.recoverList).toBeFalsy();
    expect(SLIDES_SECTION.recoverList).toBeFalsy();
  });
});
