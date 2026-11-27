'use client';

import { useEffect, useState } from 'react';
import { Eye, X } from 'lucide-react';
import { ModalBackdrop } from '@/components/ui/dialogs';
import { beginView, viewAsEligibility, viewAsUnavailable, type ViewAsEligibility } from '@/lib/view-as';
import type { ViewableWorkspace } from '@/lib/view-model';
import { viewFlagActive } from '@/lib/view-flag';
// The buttons of the person page's header (Reload, Remove) and of the settings pages (Save).
import '@/app/organizations/[orgId]/settings/users/users.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';

/** The workspaces to view, with why there is none (a bare list: no reason). */
export type ViewableWorkspaces = (personId: string) => Promise<ViewableWorkspace[] | ViewAsEligibility>;

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
 * workspace (the server's list, empty when none). The button opens a modal: a picker of those
 * workspaces, this page's workspace preselected; Start asks the server and loads the workspace as
 * the person sees it. Nothing is decided here: a refusal is the server's words.
 */
export function ViewAsControl({
  personId,
  name,
  workspaceId,
  returnTo = here,
  viewable = (id) => viewAsEligibility(id),
  start = beginView,
}: Props) {
  const [workspaces, setWorkspaces] = useState<ViewableWorkspace[]>([]);
  // Why no workspace may be viewed (shown on a disabled button); null: nothing to say, nothing shown.
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [pick, setPick] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setOpen(false);
    // No view starts from inside a view (the server answers none), so nothing is asked.
    if (viewFlagActive()) return;
    setUnavailable(null);
    viewable(personId).then(
      (found) => {
        if (cancelled) return;
        const eligibility = Array.isArray(found) ? { workspaces: found, reason: null } : found;
        setWorkspaces(eligibility.workspaces);
        setUnavailable(eligibility.workspaces.length ? null : viewAsUnavailable(name, eligibility));
      },
      () => {
        if (cancelled) return;
        setWorkspaces([]);
        setUnavailable(null);
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personId]);

  if (workspaces.length === 0) {
    // No workspace to view: the button says why, disabled; nothing when there is no reason to give.
    if (!unavailable) return null;
    return (
      <div
        className="access-view-as access-view-as-unavailable"
        data-view-as-control=""
        data-unavailable=""
        // Focusable: the reason shows on keyboard focus too (a disabled button takes none).
        tabIndex={0}
        aria-describedby="view-as-unavailable"
      >
        <button
          type="button"
          className="org-settings-users-secondary-button"
          disabled
          aria-disabled="true"
          tabIndex={-1}
          data-action="view-as"
        >
          <Eye size={16} aria-hidden="true" />
          View as {name}
        </button>
        <span id="view-as-unavailable" role="tooltip" className="access-view-as-tooltip">
          {unavailable}
        </span>
      </div>
    );
  }

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

  const close = () => {
    if (starting) return;
    setOpen(false);
    setError(null);
  };

  return (
    <div className="access-view-as" data-view-as-control="">
      <button
        type="button"
        className="org-settings-users-secondary-button"
        onClick={() => setOpen(true)}
        data-action="view-as"
      >
        <Eye size={16} aria-hidden="true" />
        View as {name}
      </button>
      <ModalBackdrop open={open} onClose={close}>
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="view-as-title"
          className="access-view-as-dialog border border-border bg-background p-6 shadow-2xl"
        >
          <div className="flex items-start justify-between gap-4">
            <h3 id="view-as-title" className="text-base font-semibold text-foreground">
              View as {name}
            </h3>
            <button type="button" className="access-view-as-close" onClick={close} aria-label="Close" disabled={starting}>
              <X size={16} />
            </button>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Open a workspace as {name} sees it: what they may use and read there. A banner lets you stop the view.
          </p>
          <label className="mt-4 flex flex-col gap-2">
            <span className="org-settings-field-label">Workspace</span>
            <select
              className="org-settings-input"
              aria-label="Workspace to view"
              value={chosen}
              onChange={(event) => setPick(event.target.value)}
              disabled={starting}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {label(w)}
                </option>
              ))}
            </select>
          </label>
          {error && (
            <p className="access-source-note mt-3" role="alert">
              {error}
            </p>
          )}
          <div className="mt-6 flex justify-end gap-2">
            <button type="button" className="org-settings-users-secondary-button" disabled={starting} onClick={close}>
              Cancel
            </button>
            <button type="button" className="org-settings-primary-button" disabled={starting} onClick={() => void go()}>
              {starting ? 'Starting…' : 'Start'}
            </button>
          </div>
        </div>
      </ModalBackdrop>
    </div>
  );
}
