import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'events-view.tsx'), 'utf8');

describe('System › Events', () => {
  it('shows the feed beside the graph of the process it selects', () => {
    expect(src).toContain('<EventsFeedPanel />');
    expect(src).toContain('<EventGraphCanvas');
  });

  it('shows the raw payload through EventsJsonCanvas, not a second editor', () => {
    expect(src).toContain('<EventsJsonCanvas event={selectedEvent} />');
    expect(src).toContain('setShowRaw((v) => !v)');
    expect(src).not.toContain('@monaco-editor/react');
    expect(src).not.toContain('<pre');
  });
});
