import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'sheets-filmstrip.tsx'),
  'utf8',
);

describe('SheetsTabStrip', () => {
  it('is a vertical tab strip without command chrome', () => {
    expect(src).toContain('data-testid="sheets-tab-strip"');
    expect(src).toContain('aria-label="Sheet tabs"');
    expect(src).toContain('flex-col');
    expect(src).toContain('overflow-y-auto');
    expect(src).toContain('SheetsTabThumb');
    expect(src).toContain('onReorder');
    expect(src).not.toContain('onInsert');
    expect(src).not.toContain('onDelete');
    expect(src).not.toContain('onDuplicate');
    expect(src).not.toContain('Insert layout');
  });
});
