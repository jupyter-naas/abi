import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'page.tsx'), 'utf8');

describe('sections editor page', () => {
  it('publishes the outline to the sidebar and keeps section actions on the menus', () => {
    expect(src).not.toContain("from '@/components/documents/documents-filmstrip'");
    expect(src).toContain('setOutline');
    expect(src).toContain('setReorderOpenDocument');
    expect(src).toContain('onInsert={insertBlock}');
    expect(src).toContain('applyDocumentCommands');
    expect(src).toContain('onDuplicateSection');
    expect(src).toContain('onDeleteSection');
    expect(src).toContain('onExportHtml');
    expect(src).toContain("from '@/components/monaco/monaco-editor'");
    expect(src).not.toContain('@monaco-editor/react');
    expect(src).toContain("pushOfficeCreate(router, 'document'");
    expect(src).not.toContain('setCreating(true)');
  });

  it('acknowledges only the saved revision through the shared save queue', () => {
    expect(src).toContain("from '@/lib/office-save-queue'");
    expect(src).toContain('createOfficeSaveQueue(');
    expect(src).toContain('queue.dispose()');
    expect(src).toContain("outcome.status === 'stale' || queue !== saveQueueRef.current");
    expect(src).toContain('setDirty(queue.isDirty())');
    expect(src.match(/saveQueueRef\.current\?\.edit\(/g)?.length).toBe(2);
  });
});
