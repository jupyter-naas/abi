/**
 * What the web knows of a view, without a call to the server: its shape, the refusals it makes,
 * the time left. No import of the stores, which read it.
 */

export type ViewAs = {
  person: { id: string; name: string };
  workspace: { id: string; name: string };
  /** When the view ends, ISO. */
  ends_at: string;
  /** When the identity provider's groups were recorded; null: the person's stored groups only. */
  groups_from: string | null;
};

export type ViewableWorkspace = {
  id: string;
  name: string;
  organization: { id: string; name: string } | null;
};

/** The view a `/session` answer holds, or null for none (or anything unreadable). */
export function parseView(value: unknown): ViewAs | null {
  if (!value || typeof value !== 'object') return null;
  const v = value as Record<string, unknown>;
  const person = v.person as Record<string, unknown> | undefined;
  const workspace = v.workspace as Record<string, unknown> | undefined;
  if (typeof person?.id !== 'string' || typeof workspace?.id !== 'string' || typeof v.ends_at !== 'string') return null;
  return {
    person: { id: person.id, name: typeof person.name === 'string' && person.name ? person.name : person.id },
    workspace: { id: workspace.id, name: typeof workspace.name === 'string' && workspace.name ? workspace.name : workspace.id },
    ends_at: v.ends_at,
    groups_from: typeof v.groups_from === 'string' ? v.groups_from : null,
  };
}

/** A refusal of the view's: the server's message is shown as it is. */
export const VIEW_REFUSAL_PREFIXES = ['Read-only:', 'Outside this view:'];

export function isViewRefusal(detail: unknown): detail is string {
  return typeof detail === 'string' && VIEW_REFUSAL_PREFIXES.some((prefix) => detail.startsWith(prefix));
}

/** The message of a 403 that is the view's refusal, else null. The response is left unread. */
export async function viewRefusalMessage(response: Response): Promise<string | null> {
  if (response.status !== 403) return null;
  try {
    const body = await response.clone().json();
    return isViewRefusal(body?.detail) ? body.detail : null;
  } catch {
    return null;
  }
}

type RefusalListener = (message: string) => void;
const refusalListeners = new Set<RefusalListener>();

/** Subscribe to the refusals (the banner's toast); returns the unsubscribe. */
export function onViewRefusal(listener: RefusalListener): () => void {
  refusalListeners.add(listener);
  return () => refusalListeners.delete(listener);
}

export function announceViewRefusal(message: string): void {
  for (const listener of refusalListeners) listener(message);
}

/** Minutes left, rounded up, never below zero. */
export function minutesLeft(endsAt: string, now: number = Date.now()): number {
  const ms = new Date(endsAt).getTime() - now;
  return Number.isFinite(ms) ? Math.max(0, Math.ceil(ms / 60000)) : 0;
}

/** Load a page in this browser (a full load: nothing in memory survives it). A seam for tests. */
export const navigation = {
  go: (path: string) => window.location.assign(path),
  reload: () => window.location.reload(),
};

