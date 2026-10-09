import { describe, expect, it } from 'vitest';

import { composerSlashSuggestions, type ComposerSlashSkill } from './composer-slash';

const skills: ComposerSlashSkill[] = [
  {
    slug: 'slides',
    name: 'Slides',
    enabled: true,
    lastUsedAt: '2026-03-01T00:00:00.000Z',
  },
  {
    slug: 'skill-creator',
    name: 'Skill creator',
    enabled: true,
    lastUsedAt: '2026-01-01T00:00:00.000Z',
  },
  {
    slug: 'sheets',
    name: 'Sheets',
    enabled: true,
    lastUsedAt: null,
  },
  {
    slug: 'documents',
    name: 'Documents',
    enabled: false,
    lastUsedAt: '2026-04-01T00:00:00.000Z',
  },
  {
    slug: 'web-research',
    name: 'Web research',
    enabled: true,
    lastUsedAt: null,
  },
];

const slugs = (input: string, catalog: readonly ComposerSlashSkill[] | null = skills) =>
  composerSlashSuggestions(input, catalog).map((row) => row.slug);

describe('composerSlashSuggestions', () => {
  it('lists enabled skill slugs for a bare slash and stays quiet otherwise', () => {
    expect(slugs('')).toEqual([]);
    expect(slugs('   ')).toEqual([]);
    expect(slugs('hello')).toEqual([]);
    expect(slugs('/slides deck')).toEqual([]);
    expect(slugs('/ slides')).toEqual([]);
    expect(slugs('/')).toEqual(['slides', 'skill-creator', 'sheets', 'web-research']);
    expect(slugs('/')).not.toContain('documents');
  });

  it('narrows /sl to slides', () => {
    expect(composerSlashSuggestions('/sl', skills)).toEqual([{ slug: 'slides', name: 'Slides' }]);
    expect(slugs('/SL')).toEqual(['slides']);
  });

  it('does not drop a finished command', () => {
    expect(composerSlashSuggestions('/slides', skills)).toEqual([
      { slug: 'slides', name: 'Slides' },
    ]);
    expect(slugs('/sheets')).toEqual(['sheets']);
    expect(
      slugs('/slides', [
        ...skills,
        { slug: 'slides-extra', name: 'Slides extra', enabled: true, lastUsedAt: '2026-05-01T00:00:00.000Z' },
      ]),
    ).toEqual(['slides-extra', 'slides']);
  });

  it('skips disabled skills and still matches inside a slug', () => {
    expect(slugs('/doc')).toEqual([]);
    expect(slugs('/she')).toEqual(['sheets']);
    expect(
      composerSlashSuggestions('/research', [
        { slug: 'web-research', name: 'Web research', enabled: true, lastUsedAt: null },
      ]),
    ).toEqual([{ slug: 'web-research', name: 'Web research' }]);
  });
});
