import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'page.tsx'), 'utf8');

describe('sheets editor page', () => {
  it('publishes tab strip state to the sidebar and wires tab + XLSX actions on the menus', () => {
    expect(src).not.toContain('SheetsFilmstrip');
    expect(src).toContain('setFilmstrip');
    expect(src).toContain('setReorderOpenWorkbook');
    expect(src).toContain('onInsertTab');
    expect(src).toContain('onDuplicateTab');
    expect(src).toContain('onDeleteTab');
    expect(src).toContain('onExportXlsx');
    expect(src).toContain('onExportHtml');
    expect(src).not.toContain('onExportPptx');
    expect(src).not.toContain('exportPptx');
    expect(src).toContain("from '@/components/monaco/monaco-editor'");
    expect(src).not.toContain('@monaco-editor/react');
  });
});
