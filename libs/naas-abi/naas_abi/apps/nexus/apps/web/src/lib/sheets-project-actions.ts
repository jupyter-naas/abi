import { sheetsApiErrorMessage } from '@/lib/create-sheets-project';
import { authFetch } from '@/stores/auth';
import { dispatchSheetsWorkbookUpdated, useSheetsStore, type SheetsProject } from '@/stores/sheets';

export type SheetsProjectPatch = {
  title?: string;
  archived?: boolean;
};

export function isSheetsProjectArchived(project: Pick<SheetsProject, 'archived'>): boolean {
  return Boolean(project.archived);
}

export function partitionSheetsProjects(projects: SheetsProject[]): {
  active: SheetsProject[];
  archived: SheetsProject[];
} {
  const active: SheetsProject[] = [];
  const archived: SheetsProject[] = [];
  for (const project of projects) {
    if (!project?.slug) continue;
    if (isSheetsProjectArchived(project)) archived.push(project);
    else active.push(project);
  }
  return { active, archived };
}

export async function patchSheetsProject(
  workspaceId: string,
  slug: string,
  patch: SheetsProjectPatch,
): Promise<SheetsProject> {
  const res = await authFetch(`/api/sheets/projects/${encodeURIComponent(slug)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace_id: workspaceId, ...patch }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(sheetsApiErrorMessage(body.detail, `Failed (${res.status})`));
  }
  const project = (await res.json()) as SheetsProject;
  if (patch.title && useSheetsStore.getState().selectedSlug === slug) {
    useSheetsStore.getState().setSelectedTitle(project.title);
  }
  dispatchSheetsWorkbookUpdated({ slug });
  return project;
}
