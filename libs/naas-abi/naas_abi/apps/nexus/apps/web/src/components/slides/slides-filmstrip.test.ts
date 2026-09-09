import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'slides-filmstrip.tsx'),
  'utf8',
);

describe('SlidesFilmstrip', () => {
  it('is a vertical thumb strip without command chrome', () => {
    expect(src).toContain('data-testid="slides-filmstrip"');
    expect(src).toContain('data-orientation="vertical"');
    expect(src).toContain('flex-col');
    expect(src).toContain('overflow-y-auto');
    expect(src).toContain('aspect-video');
    expect(src).toContain('onReorder');
    expect(src).not.toContain('onInsert');
    expect(src).not.toContain('onDelete');
    expect(src).not.toContain('onDuplicate');
    expect(src).not.toContain('Insert layout');
  });
});
