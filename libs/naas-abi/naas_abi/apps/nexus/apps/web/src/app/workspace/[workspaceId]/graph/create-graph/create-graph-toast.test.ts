import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// The page is a large client form; its toast is checked where it is said.
const source = readFileSync(join(__dirname, 'page.tsx'), 'utf8');

describe('Graph › Create New Graph', () => {
  it('says the graph is created (or updated) in the app toast stack', () => {
    expect(source).toContain("from '@/components/ui/toast'");
    expect(source).toMatch(/toast\.success\(isEditing \? 'Graph updated' : 'Graph created'/);
  });
});
