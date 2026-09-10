import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'page.tsx'), 'utf8');

describe('admin events page', () => {
  it('mounts JSON view through EventsJsonCanvas, not a second editor', () => {
    expect(src).toContain('EventsJsonCanvas');
    expect(src).toContain("view === 'json'");
    expect(src).toContain("onViewJson={() => setView('json')}");
    expect(src).not.toContain('@monaco-editor/react');
  });
});
