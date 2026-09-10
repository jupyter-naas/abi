import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'monaco-editor.tsx'), 'utf8');

describe('MonacoEditor', () => {
  it('loads the shared @monaco-editor/react client bundle', () => {
    expect(src).toContain("import('@monaco-editor/react')");
    expect(src).toContain('ssr: false');
    expect(src).toContain('vs-dark');
  });
});
