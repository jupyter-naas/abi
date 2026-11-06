/**
 * View as: the client of the server's view (`/api/iam/view-as`, `services/view_as/AGENTS.md`), and
 * the small rules the web keeps for it. The server decides who may view whom and answers everything
 * as the person; the web starts and stops the view, reloads around it, and keeps nothing of it.
 */
import { getApiUrl } from '@/lib/config';
import { getWorkspaceHomePath } from '@/lib/feature-access';
import { authFetch } from '@/stores/auth';
import { clearViewFlag, readViewFlag, setViewFlag } from './view-flag';
import type { ViewAs, ViewableWorkspace } from './view-model';
import { navigation, parseView } from './view-model';

export type { ViewAs, ViewableWorkspace } from './view-model';

export const VIEW_AS_API = '/api/iam/view-as';

export class ViewAsError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ViewAsError';
    this.status = status;
  }
}

/** The server's words for a refusal: its `detail`, else a sentence for the status. */
async function failure(response: Response, fallback: string): Promise<ViewAsError> {
  let detail = '';
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') detail = body.detail;
  } catch {
    // no JSON body
  }
  return new ViewAsError(detail || fallback, response.status);
}

/** The workspaces where the caller may view as that person (IAM's answer); empty when none. */
export async function listViewableWorkspaces(
  personId: string,
  fetcher: typeof authFetch = authFetch,
): Promise<ViewableWorkspace[]> {
  const response = await fetcher(`${VIEW_AS_API}/workspaces?principal_id=${encodeURIComponent(personId)}`);
  if (!response.ok) throw await failure(response, 'Could not read the workspaces to view.');
  const data = await response.json();
  return Array.isArray(data) ? (data as ViewableWorkspace[]) : [];
}

export async function startView(
  personId: string,
  workspaceId: string,
  fetcher: typeof authFetch = authFetch,
): Promise<ViewAs> {
  const response = await fetcher(VIEW_AS_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ principal_id: personId, workspace_id: workspaceId }),
  });
  if (!response.ok) throw await failure(response, 'Could not start the view.');
  const view = parseView(await response.json());
  if (!view) throw new ViewAsError('The server did not describe the view.', response.status);
  return view;
}

export async function stopView(fetcher: typeof authFetch = authFetch): Promise<void> {
  const response = await fetcher(VIEW_AS_API, { method: 'DELETE' });
  if (!response.ok) throw await failure(response, 'Could not stop the view.');
}

/** Where the web lands in a view: the viewed workspace's Home, a page every workspace has
 *  (`/workspace/<id>` itself has none). */
export function viewLanding(workspaceId: string): string {
  return getWorkspaceHomePath(encodeURIComponent(workspaceId));
}

/** The person's page, as the level the view was started from shows it. */
export function personPagePath(personId: string, view?: { workspaceId: string } | null): string {
  const query = `?section=people&person=${encodeURIComponent(personId)}`;
  return view?.workspaceId
    ? `/workspace/${encodeURIComponent(view.workspaceId)}/settings/permissions${query}`
    : `/settings/roles${query}`;
}

/**
 * Begin a view for the page that asked: the server starts it, the flag is raised (so the stores keep
 * nothing from the first byte of the next page), and the browser loads the workspace.
 */
export async function beginView(personId: string, workspaceId: string, returnTo: string): Promise<void> {
  const view = await startView(personId, workspaceId);
  setViewFlag({ workspaceId: view.workspace.id, returnTo }, view.ends_at);
  navigation.go(viewLanding(view.workspace.id));
}

/**
 * End the view: the server forgets it, the flag goes, and the browser loads the person's page, so
 * nothing of the view (nor of the viewer's own pages read in it) stays in memory.
 */
export async function endView(view: ViewAs): Promise<void> {
  const flag = readViewFlag();
  await stopView();
  clearViewFlag();
  navigation.go(flag?.returnTo || personPagePath(view.person.id, { workspaceId: view.workspace.id }));
}


/**
 * Whether the server's view has ended: its `/session` answers no view (or no session). A failed
 * read says no: the browser's clock is not the server's, so the page reloads only on the server's word.
 */
export async function viewHasEnded(): Promise<boolean> {
  try {
    const response = await fetch(`${getApiUrl()}/api/auth/oidc/session`, { credentials: 'include', cache: 'no-store' });
    if (response.status === 401) return true;
    if (!response.ok) return false;
    return parseView((await response.json())?.view) === null;
  } catch {
    return false;
  }
}
