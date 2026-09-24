import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'page.tsx'), 'utf8');

describe('ontology Network tab wiring', () => {
  it('mounts OntologyTermNetwork so View → Connectors can draw right-angle elbows', () => {
    expect(src).toMatch(/import \{ OntologyTermNetwork \}/);
    expect(src).toContain('<OntologyTermNetwork');
    // TermDetailNetwork is the Details pin (instance-style circles); it ignores connectors.
    expect(src).not.toMatch(/TermDetailNetwork layout="page"/);
  });
});
