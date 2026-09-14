import { documentsApiErrorMessage } from '@/lib/create-documents-project';
import {
  autoDocumentTitle,
  isPlaceholderDocumentTitle,
  shouldAutoTitleDocument,
} from '@/lib/office-auto-title';
import { authFetch } from '@/stores/auth';
import { dispatchDocumentUpdated, useDocumentsStore, type DocumentsProject } from '@/stores/documents';

export type DocumentsProjectPatch = {
  title?: string;
  archived?: boolean;
};

export function isDocumentsProjectArchived(project: Pick<DocumentsProject, 'archived'>): boolean {
  return Boolean(project.archived);
}

export function partitionDocumentsProjects(projects: DocumentsProject[]): {
  active: DocumentsProject[];
  archived: DocumentsProject[];
} {
  const active: DocumentsProject[] = [];
  const archived: DocumentsProject[] = [];
  for (const project of projects) {
    if (!project?.slug) continue;
    if (isDocumentsProjectArchived(project)) archived.push(project);
    else active.push(project);
  }
  return { active, archived };
}

export async function patchDocumentsProject(
  workspaceId: string,
  slug: string,
  patch: DocumentsProjectPatch,
): Promise<DocumentsProject> {
  const res = await authFetch(`/api/documents/projects/${encodeURIComponent(slug)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace_id: workspaceId, ...patch }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(documentsApiErrorMessage(body.detail, `Failed (${res.status})`));
  }
  const project = (await res.json()) as DocumentsProject;
  if (patch.title && useDocumentsStore.getState().selectedSlug === slug) {
    useDocumentsStore.getState().setSelectedTitle(project.title);
  }
  dispatchDocumentUpdated({ slug, title: patch.title ? project.title : undefined });
  return project;
}

export async function renameDocumentsProjectViaCommand(
  workspaceId: string,
  slug: string,
  title: string,
): Promise<string> {
  const res = await authFetch(`/api/documents/projects/${encodeURIComponent(slug)}/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workspace_id: workspaceId,
      requests: [{ type: 'rename_document', title }],
    }),
  });
  const payload = (await res.json().catch(() => ({}))) as {
    title?: string;
    detail?: unknown;
  };
  if (!res.ok) {
    throw new Error(documentsApiErrorMessage(payload.detail, `Failed (${res.status})`));
  }
  const nextTitle = (payload.title || title).trim();
  if (useDocumentsStore.getState().selectedSlug === slug) {
    useDocumentsStore.getState().setSelectedTitle(nextTitle);
  }
  dispatchDocumentUpdated({ slug, title: nextTitle, source: 'rename_document' });
  return nextTitle;
}

export async function autoTitleOpenDocumentIfNeeded(opts: {
  workspaceId: string;
  slug: string;
  title?: string | null;
  brief: string;
}): Promise<string | null> {
  const brief = (opts.brief || '').trim();
  if (!opts.workspaceId || !opts.slug || !brief || brief.startsWith('/')) return null;
  if (!shouldAutoTitleDocument(opts.title, opts.slug)) return null;
  const next = autoDocumentTitle(brief);
  if (!next || isPlaceholderDocumentTitle(next)) return null;
  useDocumentsStore.getState().setSelectedTitle(next);
  dispatchDocumentUpdated({ slug: opts.slug, title: next, source: 'auto_title' });
  try {
    return await renameDocumentsProjectViaCommand(opts.workspaceId, opts.slug, next);
  } catch {
    return next;
  }
}
