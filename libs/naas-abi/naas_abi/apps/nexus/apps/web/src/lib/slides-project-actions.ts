import { slidesApiErrorMessage } from '@/lib/create-slides-project';
import { authFetch } from '@/stores/auth';
import { dispatchSlidesDeckUpdated, useSlidesStore, type SlidesProject } from '@/stores/slides';

export type SlidesProjectPatch = {
  title?: string;
  archived?: boolean;
};

export function isSlidesProjectArchived(project: Pick<SlidesProject, 'archived'>): boolean {
  return Boolean(project.archived);
}

export function partitionSlidesProjects(projects: SlidesProject[]): {
  active: SlidesProject[];
  archived: SlidesProject[];
} {
  const active: SlidesProject[] = [];
  const archived: SlidesProject[] = [];
  for (const project of projects) {
    if (!project?.slug) continue;
    if (isSlidesProjectArchived(project)) archived.push(project);
    else active.push(project);
  }
  return { active, archived };
}

export async function patchSlidesProject(
  workspaceId: string,
  slug: string,
  patch: SlidesProjectPatch,
): Promise<SlidesProject> {
  const res = await authFetch(`/api/slides/projects/${encodeURIComponent(slug)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace_id: workspaceId, ...patch }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(slidesApiErrorMessage(body.detail, `Failed (${res.status})`));
  }
  const project = (await res.json()) as SlidesProject;
  if (patch.title && useSlidesStore.getState().selectedSlug === slug) {
    useSlidesStore.getState().setSelectedTitle(project.title);
  }
  dispatchSlidesDeckUpdated({ slug });
  return project;
}
