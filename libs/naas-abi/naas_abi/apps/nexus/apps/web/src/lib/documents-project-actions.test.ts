import { describe, expect, it } from 'vitest';
import type { DocumentsProject } from '@/stores/documents';
import { isDocumentsProjectArchived, partitionDocumentsProjects } from './documents-project-actions';

function project(over: Partial<DocumentsProject> & { slug: string }): DocumentsProject {
  return {
    title: over.title ?? over.slug,
    branch: 'main',
    document_path: `documents/${over.slug}/document.html`,
    template_id: 'abi/minimal-light-v1',
    ...over,
  };
}

describe('isDocumentsProjectArchived', () => {
  it('treats a missing flag as active, the way older project.json rows do', () => {
    expect(isDocumentsProjectArchived(project({ slug: 'a' }))).toBe(false);
    expect(isDocumentsProjectArchived(project({ slug: 'b', archived: false }))).toBe(false);
    expect(isDocumentsProjectArchived(project({ slug: 'c', archived: true }))).toBe(true);
  });
});

describe('partitionDocumentsProjects', () => {
  it('splits the default gallery list from Archived', () => {
    const { active, archived } = partitionDocumentsProjects([
      project({ slug: 'live', title: 'Live' }),
      project({ slug: 'old', title: 'Old', archived: true }),
      project({ slug: '' }),
    ]);
    expect(active.map((row) => row.slug)).toEqual(['live']);
    expect(archived.map((row) => row.slug)).toEqual(['old']);
  });
});
