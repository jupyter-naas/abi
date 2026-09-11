import { authFetch } from '@/stores/auth';
import { dispatchSlidesDeckUpdated, useSlidesStore } from '@/stores/slides';
import { useWorkspaceStore } from '@/stores/workspace';
import { openFeatureAgentPane } from '@/lib/feature-agent-pane';
import {
  findSlidesPaneConversationId,
  slidesPaneConversationKey,
} from '@/lib/slides-pane-conversation';

export const DEFAULT_SLIDES_TEMPLATE_ID = 'abi/minimal-light-v1';
export const DEFAULT_SLIDES_TITLE = 'Untitled presentation';

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

/** Open the Slides pane beside the deck so the next message can edit it.
 *
 * Binds Nexus Slides when that agent is enabled in this workspace. Falls
 * back to the workspace default only when Slides is not on the roster.
 * A new deck always resets so a leftover picker choice cannot ride in.
 *
 * The composer model selection is left exactly as the user left it. The server
 * picks the model for a slides turn and reports it back on the stream's opening
 * `llm_model` frame, so the footer stays honest without the client guessing.
 */
export function openSlidesAgentPane(opts?: {
  freshChat?: boolean;
  slug?: string | null;
  title?: string | null;
}): void {
  const ws = useWorkspaceStore.getState();
  const slug = (opts?.slug ?? useSlidesStore.getState().selectedSlug ?? '').trim();
  const title = opts?.title ?? useSlidesStore.getState().selectedTitle;
  if (!opts?.freshChat && slug) {
    const workspaceId = ws.currentWorkspaceId || '';
    const boundId = workspaceId
      ? (ws.slidesPaneConversationByKey || {})[
          slidesPaneConversationKey(workspaceId, slug)
        ] ?? null
      : null;
    const found = findSlidesPaneConversationId({
      workspaceId,
      slug,
      conversations: ws.conversations,
      boundId,
      deckTitle: title,
    });
    ws.setPaneConversationId(found);
    if (found && workspaceId) {
      ws.rememberSlidesPaneConversation(workspaceId, slug, found);
    }
  }
  // An open deck always binds Slides. The workspace default has no
  // write_slides_* tools; keeping an explicit pick burns the step budget
  // on transfers.
  openFeatureAgentPane('slides', { freshChat: opts?.freshChat, resourceId: slug });
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

/** One click: seed a template (default Minimal Light), open the deck, open the pane. */
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
