import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { sheetsFilmstripEmptyCopy } from './sheets-section-views';

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'sheets-section.tsx'),
  'utf8',
);

describe('SheetsSection sidebar views', () => {
  it('copies the Ontology toolbar: Sheets and Filmstrip under the title', () => {
    expect(src).toContain('SidebarToolbar');
    expect(src).toContain('SidebarToolbarButton');
    expect(src).toContain('label="Sheets"');
    expect(src).toContain('label="Filmstrip"');
    expect(src).toContain('data-testid="sheets-sidebar-views"');
    expect(src).toContain('sheets-sidebar-view-filmstrip');
    expect(src).toContain('SheetsFilmstrip');
  });

  it('wires New workbook through startNewWorkbook', () => {
    expect(src).toContain('startNewWorkbook');
    expect(src).toContain('label="New workbook"');
    expect(src).toContain('SheetsTreeView');
  });

  it('does not treat a leftover selected slug as a loading filmstrip', () => {
    expect(sheetsFilmstripEmptyCopy(false)).toBe('Open a workbook to see sheet tabs.');
    expect(sheetsFilmstripEmptyCopy(true)).toBe('Loading sheets…');
  });
});
