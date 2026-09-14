import { authFetch } from '@/stores/auth';
import { useAgentsStore } from '@/stores/agents';
import { dispatchSheetsWorkbookUpdated, useSheetsStore } from '@/stores/sheets';
import { useWorkspaceStore } from '@/stores/workspace';
import { pickSheetsOfficeAgent } from '@/lib/pick-workspace-default-agent';

export const DEFAULT_SHEETS_TEMPLATE_ID = 'abi/grid-light-v1';
export const DEFAULT_SHEETS_TITLE = 'Untitled workbook';

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

/** Human sheets API error; never surface a raw owner/name as the cause. */
export function sheetsApiErrorMessage(detail: unknown, fallback: string): string {
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

export function untitledSheetsSlug(now = Date.now()): string {
  return `untitled-${now.toString(36)}`;
}

export type CreatedSheetsProject = {
  slug: string;
  title: string;
};

function pickSheetsPaneAgentId(): string | null {
  return pickSheetsOfficeAgent(useAgentsStore.getState().agents)?.id ?? null;
}

/** Open the Sheets pane beside the workbook so the next message can edit it.
 *
 * Binds Nexus Sheets when that agent is enabled in this workspace. Falls
 * back to the workspace default only when Sheets is not on the roster.
 * A new workbook always resets so a leftover picker choice cannot ride in.
 *
 * The composer model selection is left exactly as the user left it. The server
 * picks the model for a sheets turn and reports it back on the stream's opening
 * `llm_model` frame, so the footer stays honest without the client guessing.
 */
export function openSheetsAgentPane(opts?: {
  freshChat?: boolean;
  slug?: string | null;
  title?: string | null;
}): void {
  const ws = useWorkspaceStore.getState();
  ws.setContextPanelOpen(true);
  const slug = (opts?.slug ?? useSheetsStore.getState().selectedSlug ?? '').trim();
  const title = opts?.title ?? useSheetsStore.getState().selectedTitle;
  if (opts?.freshChat) {
    ws.setPaneConversationId(null);
    ws.clearPaneAgentExplicitSelection();
  }
  const defaultId = pickSheetsPaneAgentId();
  if (!defaultId) return;
  const agents = useAgentsStore.getState().agents;
  const currentStillValid = Boolean(
    ws.paneAgent && agents.some((a) => a.enabled && a.id === ws.paneAgent),
  );
  // An open workbook always binds Sheets. The workspace default has no
  // write_sheets_* tools; keeping an explicit pick burns the step budget
  // on transfers.
  if (slug || opts?.freshChat || !ws.paneAgentExplicitlySelected || !currentStillValid) {
    ws.setPaneAgent(defaultId);
  }
}

export async function createUntitledSheetsProject(
  workspaceId: string,
  templateId: string = DEFAULT_SHEETS_TEMPLATE_ID,
): Promise<CreatedSheetsProject> {
  let lastError = 'Failed to create workbook';
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const slug = untitledSheetsSlug(Date.now() + attempt);
    const res = await authFetch('/api/sheets/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        title: DEFAULT_SHEETS_TITLE,
        slug,
        template_id: templateId,
      }),
    });
    if (res.ok) {
      const created = (await res.json()) as { slug: string; title?: string };
      return {
        slug: created.slug,
        title: created.title || DEFAULT_SHEETS_TITLE,
      };
    }
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    lastError = sheetsApiErrorMessage(body.detail, `Failed (${res.status})`);
    if (res.status !== 409 && res.status !== 422) {
      throw new Error(lastError);
    }
  }
  throw new Error(lastError);
}

/** One click: seed a template (default Minimal Light), open the workbook, open the pane. */
export async function startNewWorkbook(
  workspaceId: string,
  navigate: (href: string) => void,
  templateId: string = DEFAULT_SHEETS_TEMPLATE_ID,
): Promise<CreatedSheetsProject> {
  const created = await createUntitledSheetsProject(workspaceId, templateId);
  useSheetsStore.getState().setSelectedSlug(created.slug);
  useSheetsStore.getState().setSelectedTitle(created.title);
  openSheetsAgentPane({ freshChat: true });
  navigate(`/workspace/${workspaceId}/sheets/${created.slug}`);
  return created;
}

/** Swap the open workbook to a seed, or create a new workbook from that template. */
export async function applySheetsTemplate(
  workspaceId: string,
  templateId: string,
  openSlug: string | null,
  navigate: (href: string) => void,
): Promise<CreatedSheetsProject> {
  if (!openSlug) {
    return startNewWorkbook(workspaceId, navigate, templateId);
  }
  const res = await authFetch(
    `/api/sheets/projects/${encodeURIComponent(openSlug)}/apply-template`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_id: workspaceId, template_id: templateId }),
    },
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(sheetsApiErrorMessage(body.detail, `Failed (${res.status})`));
  }
  const title = useSheetsStore.getState().selectedTitle || DEFAULT_SHEETS_TITLE;
  dispatchSheetsWorkbookUpdated({ slug: openSlug, source: 'template' });
  useSheetsStore.getState().requestWorkbookRefresh(openSlug);
  openSheetsAgentPane();
  return { slug: openSlug, title };
}
