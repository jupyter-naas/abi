import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'page.tsx'), 'utf8');

describe('sections editor page', () => {
  it('publishes the outline to the sidebar and keeps section actions on the menus', () => {
    expect(src).not.toContain('DocumentsOutline');
    expect(src).toContain('setOutline');
    expect(src).toContain('setReorderOpenDocument');
    expect(src).toContain('onInsertSection');
    expect(src).toContain('onDuplicateSection');
    expect(src).toContain('onDeleteSection');
    expect(src).toContain('onExportHtml');
    expect(src).toContain("from '@/components/monaco/monaco-editor'");
    expect(src).not.toContain('@monaco-editor/react');
  });
});
