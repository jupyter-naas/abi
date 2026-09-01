import { authFetch } from '@/stores/auth';
import { useAgentsStore } from '@/stores/agents';
import { dispatchSlidesDeckUpdated, useSlidesStore } from '@/stores/slides';
import { useWorkspaceStore } from '@/stores/workspace';

export const DEFAULT_SLIDES_TEMPLATE_ID = 'minimal-light-v1';
export const DEFAULT_SLIDES_TITLE = 'Untitled presentation';
export const PREFERRED_SLIDES_CHAT_MODEL = 'gpt-4.1-mini';
export const PREFERRED_SLIDES_CHAT_MODELS = ['gpt-4.1-mini', 'openai/gpt-4.1-mini'];

const REPO_ID_RE = /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/;

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

function pickAbiAgentId(): string | null {
  const agents = useAgentsStore.getState().agents;
  const abi =
    agents.find(
      (a) =>
        a.enabled &&
        (a.name === 'Abi' ||
          (typeof a.class_name === 'string' && a.class_name.toLowerCase().includes('abiagent'))),
    ) ??
    agents.find((a) => a.isDefault && a.enabled) ??
    agents.find((a) => a.enabled);
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
    unique.find((id) => !id.includes(':free')) ||
    null;
  if (!preferred) return;
  const current = useWorkspaceStore.getState().selectedChatModels[agentId];
  if (!current || current.includes(':free')) {
    useWorkspaceStore.getState().setSelectedChatModel(agentId, preferred);
  }
}

/** Open the Abi pane beside the deck so the next message can edit it. */
export function openSlidesAgentPane(opts?: { freshChat?: boolean }): void {
  const ws = useWorkspaceStore.getState();
  ws.setContextPanelOpen(true);
  if (opts?.freshChat) {
    ws.setPaneConversationId(null);
  }
  const abiId = pickAbiAgentId();
  if (abiId) {
    if (!ws.paneAgentExplicitlySelected) ws.setPaneAgent(abiId);
    pinSlidesChatModel(abiId);
  }
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

/** One click: seed a template (default Minimal Light), open the deck, open Abi. */
export async function startNewPresentation(
  workspaceId: string,
  navigate: (href: string) => void,
  templateId: string = DEFAULT_SLIDES_TEMPLATE_ID,
): Promise<CreatedSlidesProject> {
  const created = await createUntitledSlidesProject(workspaceId, templateId);
  useSlidesStore.getState().setSelectedSlug(created.slug);
  useSlidesStore.getState().setSelectedTitle(created.title);
  openSlidesAgentPane({ freshChat: true });
  navigate(`/workspace/${workspaceId}/slides/${created.slug}`);
  return created;
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
  openSlidesAgentPane();
  return { slug: openSlug, title };
}
