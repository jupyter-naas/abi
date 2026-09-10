import { authFetch } from '@/stores/auth';
import { useAgentsStore } from '@/stores/agents';
import { dispatchDocumentUpdated, useDocumentsStore } from '@/stores/documents';
import { useWorkspaceStore } from '@/stores/workspace';
import { pickDocumentsOfficeAgent } from '@/lib/pick-workspace-default-agent';
import {
  findDocumentsPaneConversationId,
  documentsPaneConversationKey,
} from '@/lib/documents-pane-conversation';

export const DEFAULT_DOCUMENTS_TEMPLATE_ID = 'abi/article-light-v1';
export const DEFAULT_DOCUMENTS_TITLE = 'Untitled document';

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

/** Human sections API error; never surface a raw owner/name as the cause. */
export function documentsApiErrorMessage(detail: unknown, fallback: string): string {
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

export function untitledDocumentSlug(now = Date.now()): string {
  return `untitled-${now.toString(36)}`;
}

export type CreatedDocumentsProject = {
  slug: string;
  title: string;
};

function pickDocumentsPaneAgentId(): string | null {
  return pickDocumentsOfficeAgent(useAgentsStore.getState().agents)?.id ?? null;
}

/** Open the Documents pane beside the document so the next message can edit it.
 *
 * Binds Nexus Documents when that agent is enabled in this workspace. Falls
 * back to the workspace default only when Documents is not on the roster.
 * A new document always resets so a leftover picker choice cannot ride in.
 *
 * The composer model selection is left exactly as the user left it. The server
 * picks the model for a sections turn and reports it back on the stream's opening
 * `llm_model` frame, so the footer stays honest without the client guessing.
 */
export function openDocumentsAgentPane(opts?: {
  freshChat?: boolean;
  slug?: string | null;
  title?: string | null;
}): void {
  const ws = useWorkspaceStore.getState();
  ws.setContextPanelOpen(true);
  const slug = (opts?.slug ?? useDocumentsStore.getState().selectedSlug ?? '').trim();
  const title = opts?.title ?? useDocumentsStore.getState().selectedTitle;
  if (opts?.freshChat) {
    ws.setPaneConversationId(null);
    ws.clearPaneAgentExplicitSelection();
  } else if (slug) {
    const workspaceId = ws.currentWorkspaceId || '';
    const boundId = workspaceId
      ? (ws.documentsPaneConversationByKey || {})[
          documentsPaneConversationKey(workspaceId, slug)
        ] ?? null
      : null;
    const found = findDocumentsPaneConversationId({
      workspaceId,
      slug,
      conversations: ws.conversations,
      boundId,
      documentTitle: title,
    });
    ws.setPaneConversationId(found);
    if (found && workspaceId) {
      ws.rememberDocumentsPaneConversation(workspaceId, slug, found);
    }
  }
  const defaultId = pickDocumentsPaneAgentId();
  if (!defaultId) return;
  const agents = useAgentsStore.getState().agents;
  const currentStillValid = Boolean(
    ws.paneAgent && agents.some((a) => a.enabled && a.id === ws.paneAgent),
  );
  // An open document always binds Documents. The workspace default has no
  // write_sections_* tools; keeping an explicit pick burns the step budget
  // on transfers.
  if (slug || opts?.freshChat || !ws.paneAgentExplicitlySelected || !currentStillValid) {
    ws.setPaneAgent(defaultId);
  }
}

export async function createUntitledDocumentsProject(
  workspaceId: string,
  templateId: string = DEFAULT_DOCUMENTS_TEMPLATE_ID,
): Promise<CreatedDocumentsProject> {
  let lastError = 'Failed to create document';
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const slug = untitledDocumentSlug(Date.now() + attempt);
    const res = await authFetch('/api/documents/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        title: DEFAULT_DOCUMENTS_TITLE,
        slug,
        template_id: templateId,
      }),
    });
    if (res.ok) {
      const created = (await res.json()) as { slug: string; title?: string };
      return {
        slug: created.slug,
        title: created.title || DEFAULT_DOCUMENTS_TITLE,
      };
    }
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    lastError = documentsApiErrorMessage(body.detail, `Failed (${res.status})`);
    if (res.status !== 409 && res.status !== 422) {
      throw new Error(lastError);
    }
  }
  throw new Error(lastError);
}

/** One click: seed a template (default Minimal Light), open the document, open the pane. */
export async function startNewDocument(
  workspaceId: string,
  navigate: (href: string) => void,
  templateId: string = DEFAULT_DOCUMENTS_TEMPLATE_ID,
): Promise<CreatedDocumentsProject> {
  const created = await createUntitledDocumentsProject(workspaceId, templateId);
  useDocumentsStore.getState().setSelectedSlug(created.slug);
  useDocumentsStore.getState().setSelectedTitle(created.title);
  openDocumentsAgentPane({ freshChat: true });
  navigate(`/workspace/${workspaceId}/documents/${created.slug}`);
  return created;
}

/** Swap the open document to a seed, or create a new document from that template. */
export async function applyDocumentsTemplate(
  workspaceId: string,
  templateId: string,
  openSlug: string | null,
  navigate: (href: string) => void,
): Promise<CreatedDocumentsProject> {
  if (!openSlug) {
    return startNewDocument(workspaceId, navigate, templateId);
  }
  const res = await authFetch(
    `/api/documents/projects/${encodeURIComponent(openSlug)}/apply-template`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, template_id: templateId }),
    },
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(documentsApiErrorMessage(body.detail, `Failed (${res.status})`));
  }
  const title = useDocumentsStore.getState().selectedTitle || DEFAULT_DOCUMENTS_TITLE;
  dispatchDocumentUpdated({ slug: openSlug, source: 'template' });
  useDocumentsStore.getState().requestDocumentRefresh(openSlug);
  openDocumentsAgentPane();
  return { slug: openSlug, title };
}
