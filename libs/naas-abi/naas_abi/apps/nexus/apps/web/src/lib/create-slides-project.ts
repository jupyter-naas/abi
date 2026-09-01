import { authFetch } from '@/stores/auth';
import { useAgentsStore } from '@/stores/agents';
import { dispatchSlidesDeckUpdated, useSlidesStore } from '@/stores/slides';
import { useWorkspaceStore } from '@/stores/workspace';

export const DEFAULT_SLIDES_TEMPLATE_ID = 'minimal-light-v1';
export const DEFAULT_SLIDES_TITLE = 'Untitled presentation';
export const PREFERRED_SLIDES_CHAT_MODEL = 'anthropic/claude-sonnet-5';
export const PREFERRED_SLIDES_CHAT_MODELS = [
  'anthropic/claude-sonnet-5',
  'claude-sonnet-5',
];

const REPO_ID_RE = /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/;

export type SlidesAgentPick = {
  id: string;
  name: string;
  class_name?: string | null;
  enabled?: boolean;
  isDefault?: boolean;
};

/** FastAPI `detail` is a string, validation list, or `{msg}` object. */
export function parseFastApiDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail.trim();
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item.trim();
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: unknown }).msg).trim();
        }
        return '';
      })
      .filter(Boolean)
      .join('; ');
  }
  if (detail && typeof detail === 'object') {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.msg === 'string') return obj.msg.trim();
    if (typeof obj.message === 'string') return obj.message.trim();
    if ('detail' in obj) return parseFastApiDetail(obj.detail);
  }
  return '';
}

/** Human slides API error; never surface a raw owner/name as the cause. */
export function slidesApiErrorMessage(detail: unknown, fallback: string): string {
  const raw = parseFastApiDetail(detail);
  if (!raw) return fallback;
  if (REPO_ID_RE.test(raw)) {
    return (
      `Git repo '${raw}' is missing. Forgejo is not configured, ` +
      'or coding-init did not seed it.'
    );
  }
  return raw;
}

export function untitledSlidesSlug(now = Date.now()): string {
  return `untitled-${now.toString(36)}`;
}

export type CreatedSlidesProject = {
  slug: string;
  title: string;
};

export function isSlidesAgent(agent: SlidesAgentPick): boolean {
  const className = (agent.class_name || '').toLowerCase();
  return (
    agent.name === 'Slides' ||
    agent.name === 'SlidesAgent' ||
    className.includes('slidesagent')
  );
}

export function isWeakSlidesModelId(id: string | null | undefined): boolean {
  const raw = (id || '').toLowerCase();
  if (!raw) return true;
  return raw.includes('mini') || raw.includes(':free') || raw.includes('nano');
}

/** Prefer SlidesAgent. Abi is fallback only if Slides is not registered yet. */
export function pickSlidesAgentId(agents: SlidesAgentPick[]): string | null {
  const enabled = agents.filter((a) => a.enabled !== false);
  const slides = enabled.find(isSlidesAgent);
  if (slides) return slides.id;
  const abi = enabled.find(
    (a) =>
      a.name === 'Abi' ||
      (typeof a.class_name === 'string' && a.class_name.toLowerCase().includes('abiagent')),
  );
  return abi?.id ?? null;
}

function pinSlidesChatModel(agentId: string): void {
  const agent = useAgentsStore.getState().agents.find((a) => a.id === agentId);
  const available = [
    ...(agent?.modelIds ?? []),
    agent?.resolvedModelId,
    agent?.modelId,
    ...PREFERRED_SLIDES_CHAT_MODELS,
  ].filter((id): id is string => Boolean(id));
  const unique = [...new Set(available)];
  const preferred =
    unique.find((id) => PREFERRED_SLIDES_CHAT_MODELS.includes(id)) ||
    unique.find((id) => !isWeakSlidesModelId(id)) ||
    null;
  if (!preferred) return;
  const current = useWorkspaceStore.getState().selectedChatModels[agentId];
  if (isWeakSlidesModelId(current)) {
    useWorkspaceStore.getState().setSelectedChatModel(agentId, preferred);
  }
}

/** Open the Slides pane beside the deck so the next message can edit it. */
export function openSlidesAgentPane(opts?: { freshChat?: boolean }): void {
  const ws = useWorkspaceStore.getState();
  ws.setContextPanelOpen(true);
  if (opts?.freshChat) {
    ws.setPaneConversationId(null);
  }
  const slidesId = pickSlidesAgentId(useAgentsStore.getState().agents);
  if (slidesId) {
    if (!ws.paneAgentExplicitlySelected) ws.setPaneAgent(slidesId);
    pinSlidesChatModel(slidesId);
  }
}

export async function bindSlidesAgentPane(opts?: {
  freshChat?: boolean;
  workspaceId?: string;
}): Promise<void> {
  const wsId = opts?.workspaceId || useWorkspaceStore.getState().currentWorkspaceId;
  if (wsId) {
    await useAgentsStore.getState().fetchAgents(wsId, true);
  }
  openSlidesAgentPane(opts);
}

export async function createUntitledSlidesProject(
  workspaceId: string,
  templateId: string = DEFAULT_SLIDES_TEMPLATE_ID,
): Promise<CreatedSlidesProject> {
  let lastError = 'Failed to create presentation';
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const slug = untitledSlidesSlug(Date.now() + attempt);
    const res = await authFetch('/api/slides/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        title: DEFAULT_SLIDES_TITLE,
        slug,
        template_id: templateId,
      }),
    });
    if (res.ok) {
      const created = (await res.json()) as { slug: string; title?: string };
      return {
        slug: created.slug,
        title: created.title || DEFAULT_SLIDES_TITLE,
      };
    }
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    lastError = slidesApiErrorMessage(body.detail, `Failed (${res.status})`);
    if (res.status !== 409 && res.status !== 422) {
      throw new Error(lastError);
    }
  }
  throw new Error(lastError);
}

/** One click: seed a template (default Minimal Light), open the deck, open Slides. */
export async function startNewPresentation(
  workspaceId: string,
  navigate: (href: string) => void,
  templateId: string = DEFAULT_SLIDES_TEMPLATE_ID,
): Promise<CreatedSlidesProject> {
  const created = await createUntitledSlidesProject(workspaceId, templateId);
  useSlidesStore.getState().setSelectedSlug(created.slug);
  useSlidesStore.getState().setSelectedTitle(created.title);
  await bindSlidesAgentPane({ freshChat: true, workspaceId });
  navigate(`/workspace/${workspaceId}/slides/${created.slug}`);
  return created;
}

export function sanitizeSlidesTitle(raw: string): string {
  return raw.replace(/\s+/g, ' ').trim().slice(0, 120);
}

/** Persist the folder title in project.json. Slug and branch stay the same. */
export async function renameSlidesProject(
  workspaceId: string,
  slug: string,
  rawTitle: string,
): Promise<CreatedSlidesProject> {
  const title = sanitizeSlidesTitle(rawTitle);
  if (!title) {
    throw new Error('Title cannot be empty.');
  }
  const res = await authFetch(`/api/slides/projects/${encodeURIComponent(slug)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace_id: workspaceId, title }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(slidesApiErrorMessage(body.detail, `Failed (${res.status})`));
  }
  const updated = (await res.json()) as { slug: string; title?: string };
  const nextTitle = updated.title || title;
  if (useSlidesStore.getState().selectedSlug === slug) {
    useSlidesStore.getState().setSelectedTitle(nextTitle);
  }
  return { slug: updated.slug || slug, title: nextTitle };
}

/** Swap the open deck to a seed, or create a new presentation from that template. */
export async function applySlidesTemplate(
  workspaceId: string,
  templateId: string,
  openSlug: string | null,
  navigate: (href: string) => void,
): Promise<CreatedSlidesProject> {
  if (!openSlug) {
    return startNewPresentation(workspaceId, navigate, templateId);
  }
  const res = await authFetch(
    `/api/slides/projects/${encodeURIComponent(openSlug)}/apply-template`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, template_id: templateId }),
    },
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(slidesApiErrorMessage(body.detail, `Failed (${res.status})`));
  }
  const title = useSlidesStore.getState().selectedTitle || DEFAULT_SLIDES_TITLE;
  dispatchSlidesDeckUpdated({ slug: openSlug, source: 'template' });
  useSlidesStore.getState().requestDeckRefresh(openSlug);
  await bindSlidesAgentPane({ workspaceId });
  return { slug: openSlug, title };
}
