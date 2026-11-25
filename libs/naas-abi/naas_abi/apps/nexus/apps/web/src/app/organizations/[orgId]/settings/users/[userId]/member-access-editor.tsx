'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { CapabilityGroupPicker, type CapabilityGroupsAt } from '@/components/invitations/invite-policy-picker';
import { LEVELS, LEVEL_EVERYWHERE_NOTE, LEVEL_LABELS, type CapabilityGroup, type Level } from '@/lib/people';
import type { AccessDraft } from './member-details';

export type OrgWorkspaceChoice = { id: string; name: string };

/**
 * A member's access in the organization (#1589): org admin, their level (in all their
 * workspaces), the workspaces they work in with "admin", and their capability groups. Edits a
 * draft the page saves with the profile.
 */
export function MemberAccessEditor({
  orgId,
  draft,
  onChange,
  workspaces,
  disabled,
  loadCapabilities,
}: {
  orgId: string;
  draft: AccessDraft;
  onChange: (draft: AccessDraft) => void;
  /** Every workspace of the organization. */
  workspaces: OrgWorkspaceChoice[];
  disabled?: boolean;
  loadCapabilities?: (at: CapabilityGroupsAt) => Promise<CapabilityGroup[]>;
}) {
  const joined = new Map(draft.workspaces.map((w) => [w.id, w]));
  const toggleJoined = (id: string, on: boolean) =>
    onChange({
      ...draft,
      workspaces: on ? [...draft.workspaces, { id, admin: false }] : draft.workspaces.filter((w) => w.id !== id),
    });
  const toggleAdmin = (id: string, admin: boolean) =>
    onChange({ ...draft, workspaces: draft.workspaces.map((w) => (w.id === id ? { ...w, admin } : w)) });
  const sorted = [...workspaces].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <section className="org-member-detail-section" aria-label="Access" data-member-access>
      <header className="org-member-detail-section-header">
        <h3>Access</h3>
        <p>
          Where they work and at which level. Org admins reach every workspace of the organization; someone in no
          workspace is one of the organization&apos;s people.
        </p>
      </header>
      <div className="account-profile-form-grid">
        <div className="account-profile-field" data-field="org-admin">
          <span className="account-profile-field-label">Organization</span>
          <Checkbox
            label="Org admin"
            checked={draft.orgAdmin}
            onCheckedChange={(on) => onChange({ ...draft, orgAdmin: on })}
            disabled={disabled}
          />
        </div>
        <div className="account-profile-field">
          <label className="account-profile-field-label" htmlFor="org-member-level">
            Level
          </label>
          <select
            id="org-member-level"
            value={draft.level ?? ''}
            onChange={(event) => onChange({ ...draft, level: (event.target.value || null) as Level | null })}
            className="account-profile-field-input"
            disabled={disabled}
            data-field="level"
          >
            {draft.level === null && <option value="">—</option>}
            {LEVELS.map((level) => (
              <option key={level} value={level}>
                {LEVEL_LABELS[level]}
              </option>
            ))}
          </select>
          <p className="org-settings-footnote" data-level-note>
            {LEVEL_EVERYWHERE_NOTE}
          </p>
        </div>
      </div>
      <div className="org-settings-users-table-wrap">
        {sorted.length === 0 ? (
          <p className="org-settings-users-no-match">No workspace in this organization.</p>
        ) : (
          <table className="org-settings-users-table org-member-detail-workspaces">
            <thead>
              <tr>
                <th>Workspace</th>
                <th>Works in it</th>
                <th>Admin</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((workspace) => {
                const access = joined.get(workspace.id);
                return (
                  <tr key={workspace.id} data-workspace={workspace.id}>
                    <td>{workspace.name}</td>
                    <td data-field="workspace-joined">
                      <Checkbox
                        aria-label={`Works in ${workspace.name}`}
                        checked={!!access}
                        onCheckedChange={(on) => toggleJoined(workspace.id, on)}
                        disabled={disabled}
                      />
                    </td>
                    <td data-field="workspace-admin">
                      <Checkbox
                        aria-label={`Admin of ${workspace.name}`}
                        checked={!!access?.admin}
                        onCheckedChange={(on) => toggleAdmin(workspace.id, on)}
                        disabled={disabled || !access}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <CapabilityGroupPicker
        at={{ organizationId: orgId }}
        value={draft.capabilities}
        onChange={(capabilities) => onChange({ ...draft, capabilities })}
        disabled={disabled}
        {...(loadCapabilities ? { load: loadCapabilities } : {})}
      />
    </section>
  );
}
