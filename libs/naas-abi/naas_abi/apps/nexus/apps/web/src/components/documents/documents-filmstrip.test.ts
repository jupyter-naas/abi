import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'documents-filmstrip.tsx'),
  'utf8',
);

describe('DocumentsOutline', () => {
  it('is a heading list without slide thumbs or command chrome', () => {
    expect(src).toContain('data-testid="documents-outline"');
    expect(src).toContain('data-orientation="vertical"');
    expect(src).toContain('flex-col');
    expect(src).toContain('overflow-y-auto');
    expect(src).toContain('Document outline');
    expect(src).not.toContain('aspect-video');
    expect(src).toContain('onReorder');
    expect(src).not.toContain('onInsert');
    expect(src).not.toContain('onDelete');
    expect(src).not.toContain('onDuplicate');
    expect(src).not.toContain('Insert layout');
  });
});
