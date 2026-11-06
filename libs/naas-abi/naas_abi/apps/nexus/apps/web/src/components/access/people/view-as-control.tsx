'use client';

import { useEffect, useState } from 'react';
import { Eye } from 'lucide-react';
import { beginView, listViewableWorkspaces } from '@/lib/view-as';
import type { ViewableWorkspace } from '@/lib/view-model';

export type ViewableWorkspaces = (personId: string) => Promise<ViewableWorkspace[]>;

type Props = {
  /** The person's IAM id. */
  personId: string;
  name: string;
  /** The workspace of the page this is opened from, if any: preselected. */
  workspaceId: string | null;
  /** The page Stop returns to (this page by default). */
  returnTo?: () => string;
  /** Lists the workspaces to view (tests pass a fake); IAM's answer by default. */
  viewable?: ViewableWorkspaces;
  /** Starts the view and loads the workspace (tests pass a fake). */
  start?: (personId: string, workspaceId: string, returnTo: string) => Promise<void>;
};

const here = () => `${window.location.pathname}${window.location.search}`;
const label = (w: ViewableWorkspace) => (w.organization ? `${w.name} · ${w.organization.name}` : w.name);

/**
 * "View as <name>", on a person's page: shown when IAM accepts a view of them in at least one
 * workspace (the server's list, empty when none). The button opens a picker of those workspaces,
 * this page's workspace preselected; Start asks the server and loads the workspace as the person
 * sees it. Nothing is decided here: a refusal is the server's words.
 */
export function ViewAsControl({
  personId,
  name,
  workspaceId,
  returnTo = here,
  viewable = (id) => listViewableWorkspaces(id),
  start = beginView,
}: Props) {
  const [workspaces, setWorkspaces] = useState<ViewableWorkspace[]>([]);
  const [open, setOpen] = useState(false);
  const [pick, setPick] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setOpen(false);
    viewable(personId).then(
      (found) => !cancelled && setWorkspaces(found),
      () => !cancelled && setWorkspaces([]),
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personId]);

  if (workspaces.length === 0) return null;

  const chosen = pick && workspaces.some((w) => w.id === pick)
    ? pick
    : (workspaces.find((w) => w.id === workspaceId) ?? workspaces[0]).id;

  const go = async () => {
    setStarting(true);
    setError(null);
    try {
      await start(personId, chosen, returnTo());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStarting(false);
    }
  };

  return (
    <div className="access-view-as" data-view-as-control="">
      {!open ? (
        <button type="button" className="access-button" onClick={() => setOpen(true)}>
          <Eye size={14} aria-hidden="true" /> View as {name}
        </button>
      ) : (
        <div className="access-view-as-picker">
          <label className="access-att-field">
            <span>View {name} in</span>
            <select
              className="access-input"
              aria-label="Workspace to view"
              value={chosen}
              onChange={(event) => setPick(event.target.value)}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {label(w)}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="access-button access-button-primary" disabled={starting} onClick={() => void go()}>
            Start
          </button>
          <button type="button" className="access-button" disabled={starting} onClick={() => setOpen(false)}>
            Cancel
          </button>
        </div>
      )}
      {error && (
        <p className="access-source-note" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
