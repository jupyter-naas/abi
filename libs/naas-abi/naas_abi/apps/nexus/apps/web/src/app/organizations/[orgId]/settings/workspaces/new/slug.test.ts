import { describe, expect, it } from 'vitest';
import { slugify, WORKSPACE_SLUG } from './slug';

describe('slugify', () => {
  it('builds slugs the API accepts', () => {
    expect(slugify('Forvis Mazars — Audit FR')).toBe('forvis-mazars-audit-fr');
    expect(slugify('  Société Générale  ')).toBe('societe-generale');
    expect(WORKSPACE_SLUG.test(slugify('AI in audit'))).toBe(true);
  });

  it('returns an empty slug when nothing is usable', () => {
    expect(slugify('—')).toBe('');
    expect(WORKSPACE_SLUG.test('a')).toBe(false); // the API needs at least two characters
  });
});
