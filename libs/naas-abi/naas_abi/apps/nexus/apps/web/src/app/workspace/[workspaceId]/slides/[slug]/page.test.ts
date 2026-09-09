import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'page.tsx'), 'utf8');

describe('slides editor page', () => {
  it('publishes the filmstrip to the sidebar and keeps slide actions on the menus', () => {
    expect(src).not.toContain('SlidesFilmstrip');
    expect(src).toContain('setFilmstrip');
    expect(src).toContain('setReorderOpenDeck');
    expect(src).toContain('onInsertSlide');
    expect(src).toContain('onDuplicateSlide');
    expect(src).toContain('onDeleteSlide');
    expect(src).toContain('onExportHtml');
  });
});
