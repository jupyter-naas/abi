import { slidesApiErrorMessage } from '@/lib/create-slides-project';
import {
  autoDeckTitle,
  isPlaceholderDeckTitle,
  shouldAutoTitleDeck,
} from '@/lib/office-auto-title';
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

export async function renameSlidesProjectViaCommand(
  workspaceId: string,
  slug: string,
  title: string,
): Promise<string> {
  const res = await authFetch(`/api/slides/projects/${encodeURIComponent(slug)}/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workspace_id: workspaceId,
      requests: [{ type: 'rename_deck', title }],
    }),
  });
  const payload = (await res.json().catch(() => ({}))) as {
    title?: string;
    detail?: unknown;
  };
  if (!res.ok) {
    throw new Error(slidesApiErrorMessage(payload.detail, `Failed (${res.status})`));
  }
  const nextTitle = (payload.title || title).trim();
  if (useSlidesStore.getState().selectedSlug === slug) {
    useSlidesStore.getState().setSelectedTitle(nextTitle);
  }
  dispatchSlidesDeckUpdated({ slug, title: nextTitle, source: 'rename_deck' });
  return nextTitle;
}

export async function autoTitleOpenDeckIfNeeded(opts: {
  workspaceId: string;
  slug: string;
  title?: string | null;
  brief: string;
}): Promise<string | null> {
  const brief = (opts.brief || '').trim();
  if (!opts.workspaceId || !opts.slug || !brief || brief.startsWith('/')) return null;
  if (!shouldAutoTitleDeck(opts.title, opts.slug)) return null;
  const next = autoDeckTitle(brief);
  if (!next || isPlaceholderDeckTitle(next)) return null;
  useSlidesStore.getState().setSelectedTitle(next);
  dispatchSlidesDeckUpdated({ slug: opts.slug, title: next, source: 'auto_title' });
  try {
    return await renameSlidesProjectViaCommand(opts.workspaceId, opts.slug, next);
  } catch {
    return next;
  }
}
