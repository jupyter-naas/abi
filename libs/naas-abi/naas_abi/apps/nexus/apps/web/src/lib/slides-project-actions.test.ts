import { describe, expect, it } from 'vitest';
import type { SlidesProject } from '@/stores/slides';
import { isSlidesProjectArchived, partitionSlidesProjects } from './slides-project-actions';

function project(over: Partial<SlidesProject> & { slug: string }): SlidesProject {
  return {
    title: over.title ?? over.slug,
    branch: 'main',
    deck_path: `slides/${over.slug}/deck.html`,
    template_id: 'abi/minimal-light-v1',
    ...over,
  };
}

describe('isSlidesProjectArchived', () => {
  it('treats a missing flag as active, the way older project.json rows do', () => {
    expect(isSlidesProjectArchived(project({ slug: 'a' }))).toBe(false);
    expect(isSlidesProjectArchived(project({ slug: 'b', archived: false }))).toBe(false);
    expect(isSlidesProjectArchived(project({ slug: 'c', archived: true }))).toBe(true);
  });
});

describe('partitionSlidesProjects', () => {
  it('splits the default gallery list from Archived', () => {
    const { active, archived } = partitionSlidesProjects([
      project({ slug: 'live', title: 'Live' }),
      project({ slug: 'old', title: 'Old', archived: true }),
      project({ slug: '' }),
    ]);
    expect(active.map((row) => row.slug)).toEqual(['live']);
    expect(archived.map((row) => row.slug)).toEqual(['old']);
  });
});
