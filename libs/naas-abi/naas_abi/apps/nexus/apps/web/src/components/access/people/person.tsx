'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import type { AttachmentView, PrincipalView } from '@/lib/iam-admin/types';
import { viewFlagActive } from '@/lib/view-flag';
import { useAuthStore } from '@/stores/auth';
import type { AccessViewProps } from '../access-props';
import type { AccessDirectory } from '../access-directory';
import { PLATFORM, organizationAccessScope, ownerOf, parseScope, workspaceAccessScope } from '../access-scope';
import { AttachForm } from '../attachments/attach-form';
import { principalLabel } from '../attachments/attachments-model';
import { holdingRows, levelLabel, roleTargetOf, scopesOf, type GroupHoldings } from '../holdings/holdings-model';
import { HoldingsTable } from '../holdings/holdings-table';
import { useActionsAt, useContainerNames } from '../policies/policy-owners';
import { changeMemberRole, type BuiltInRole, type RoleTarget } from '../roles/role-change';
import { ViewAsControl, type ViewableWorkspaces } from './view-as-control';
import './people.css';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

type Props = AccessViewProps & {
  /** The person's IAM id. */
  personId: string;
  /** Their name as the page that opened this one shows it, until IAM's is read. */
  label?: string | null;
  onClose: () => void;
  /** Changes a role (tests pass a fake); the membership routes by default. */
  changeRole?: (target: RoleTarget, userId: string, role: BuiltInRole) => Promise<void>;
  /** The workspaces to view them in (tests pass a fake); IAM's answer by default. */
  viewable?: ViewableWorkspaces;
};

type Loaded = {
  direct: AttachmentView[];
  groups: GroupHoldings[];
  notices: string[];
  profile: PrincipalView | null;
};

const targetKey = (target: RoleTarget) =>
  target.level === 'workspace' ? `workspace/${target.workspaceId}` : `organization/${target.organizationId}`;

/**
 * The person as the members of ``target`` name them, as People & roles joins them
 * (`people-model.peopleAt`): their IAM id, else, for an account linked from the old login, the
 * member with their email. Null when they are not found there, or their role there is the
 * organization's (read-only), or the members cannot be read: the role is then not changed here.
 */
async function memberAt(
  directory: AccessDirectory,
  target: RoleTarget,
  personId: string,
  email: string | null | undefined,
): Promise<string | null> {
  const scope =
    target.level === 'workspace'
      ? workspaceAccessScope(null, target.workspaceId)
      : organizationAccessScope(target.organizationId);
  try {
    const members = await directory.members(scope);
    const wanted = email?.toLowerCase();
    const found =
      members.find((m) => m.userId === personId) ??
      (wanted ? members.find((m) => m.email && m.email.toLowerCase() === wanted) : undefined);
    return found && !found.inherited ? found.userId : null;
  } catch {
    return null;
  }
}

/**
 * A person's page: every role, policy and group they hold, at every level IAM lets the viewer
 * list (`GET /attachments?principal_id=`, `GET /principals/{id}/groups` and each group's
 * attachments), whatever the level of the page it is opened from. Each row names its level as
 * the Owner column does, says whether it is direct or through which group, links to the policy
 * at its owner, and offers the detach (or, for a role, the change of role, as on Members) where
 * IAM says the viewer may. A policy is attached to them here too (the person fixed), at the
 * page's level by default or at another one they belong to: the platform, or an organization
 * or a workspace where they hold a role; only where IAM lets the viewer attach. A role changes through the membership route of its organization or
 * workspace, for the person as its members name them (``memberAt``), whatever opened the page.
 * Nexus decides nothing here.
 */
export function PersonView({
  api,
  can,
  scope,
  nonce = 0,
  open,
  directory,
  personId,
  label,
  onClose,
  changeRole = changeMemberRole,
  viewable,
}: Props) {
  const selfId = useAuthStore((s) => s.user?.id ?? null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const notices: string[] = [];
    // A view is one workspace: what the person holds there is read at its container, and what they hold at
    // the organization or the platform is outside it (``view_as/AGENTS.md``).
    const inView = viewFlagActive();
    const held = (principalId: string) =>
      api.listAttachments(inView ? { principal_id: principalId, scope: ownerOf(scope) } : { principal_id: principalId });
    // Across levels IAM answers what the viewer may list: an empty list, never a refusal.
    const [direct, groups] = await Promise.all([
      held(personId).then(
        (page) => page.items,
        (e: unknown) => {
          notices.push(`What they hold could not be read (${message(e)}).`);
          return [] as AttachmentView[];
        },
      ),
      api.principalGroups(personId).then(
        (page) => page.items,
        (e: unknown) => {
          notices.push(`Their groups could not be read (${message(e)}).`);
          return [] as PrincipalView[];
        },
      ),
    ]);
    const heldByGroups = await Promise.all(
      groups.map((group) =>
        held(group.id).then(
          (page) => ({ group, attachments: page.items }),
          (e: unknown) => {
            notices.push(`What ${principalLabel(group, group.id)} gives could not be read (${message(e)}).`);
            return { group, attachments: [] as AttachmentView[] };
          },
        ),
      ),
    );
    let profile = direct.find((a) => a.principal)?.principal ?? null;
    // A person read by id is outside a view (``view_as/AGENTS.md``): their rows name them, else the label does.
    if (!profile && !viewFlagActive()) profile = await api.getPrincipal(personId).catch(() => null);
    setLoaded({ direct, groups: heldByGroups, notices, profile });
  }, [api, personId, scope]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const rows = useMemo(() => (loaded ? holdingRows(loaded.direct, loaded.groups) : []), [loaded]);
  const here = ownerOf(scope);
  // Where a policy may be attached to them: this page's level, the platform, and each
  // organization or workspace they hold a role at (its container, not below it).
  const levels = useMemo(() => {
    // In a view the platform's level is outside it, and so is any other level.
    const found = viewFlagActive() ? [here] : here === PLATFORM ? [PLATFORM] : [here, PLATFORM];
    for (const row of rows) {
      const at = row.role && !row.via ? row.attachment.scope : null;
      if (at && !viewFlagActive() && !parseScope(at)?.below && !found.includes(at)) found.push(at);
    }
    return found;
  }, [rows, here]);
  const scopes = useMemo(
    () => [...scopesOf(rows), ...(loaded?.groups ?? []).map((g) => g.group.owner_scope ?? PLATFORM), ...levels],
    [rows, loaded, levels],
  );
  const names = useContainerNames(api, scopes, nonce);
  const actionsAt = useActionsAt(api, scopes, here, can, nonce);

  // Each organization and workspace they hold a role at: who they are among its members.
  const [members, setMembers] = useState<Record<string, string | null>>({});
  const email = loaded?.profile?.email ?? null;
  const targets = useMemo(() => {
    const found = new Map<string, RoleTarget>();
    for (const row of rows) {
      const target = row.role ? roleTargetOf(row.attachment.scope) : null;
      if (target) found.set(targetKey(target), target);
    }
    return found;
  }, [rows]);
  useEffect(() => {
    let cancelled = false;
    for (const [key, target] of targets) {
      void memberAt(directory, target, personId, email).then((id) => {
        if (!cancelled) setMembers((current) => ({ ...current, [key]: id }));
      });
    }
    return () => {
      cancelled = true;
    };
  }, [directory, targets, personId, email, nonce]);

  // The levels the viewer may attach at, this page's first; the one picked, else the first.
  const attachable = levels.filter((level) => actionsAt(level)['iam:AttachPolicy']);
  const [attachPick, setAttachPick] = useState<string | null>(null);
  const attachAt = attachPick && attachable.includes(attachPick) ? attachPick : (attachable[0] ?? null);

  const run = async (call: () => Promise<unknown>) => {
    try {
      await call();
      setError(null);
      await load();
    } catch (e) {
      setError(message(e));
    }
  };

  const name = loaded?.profile ? principalLabel(loaded.profile, personId) : label || personId;
  const shownEmail = email && email !== name ? email : null;

  return (
    <div className="access-person" data-person-page={personId}>
      <button type="button" className="access-person-back" onClick={onClose}>
        <ArrowLeft size={14} /> People &amp; roles
      </button>
      <header className="access-person-header">
        <h3 className="access-person-name">{name}</h3>
        {shownEmail && <span className="access-people-sub">{shownEmail}</span>}
        <code className="access-mono">{personId}</code>
        <ViewAsControl personId={personId} name={name} workspaceId={scope.workspaceId} viewable={viewable} />
      </header>
      {error && (
        <p className="access-source-note" role="alert">
          {error}
        </p>
      )}
      {!loaded ? (
        <p className="access-empty">Loading…</p>
      ) : (
        <>
          {loaded.notices.map((notice) => (
            <p key={notice} className="access-source-note" role="status" data-person-notice="">
              {notice}
            </p>
          ))}
          <section className="access-person-section" aria-label="Roles and policies">
            <h4 className="access-person-heading">Roles and policies, at every level</h4>
            <HoldingsTable
              rows={rows}
              names={names}
              actionsAt={actionsAt}
              here={here}
              onDetach={(a) =>
                void run(() => api.detach({ policy_id: a.policy_id, principal_id: a.principal_id, scope: a.scope }))
              }
              onOpenGroup={open?.group}
              roles={{
                memberAt: (target) => members[targetKey(target)] ?? null,
                selfId,
                change: (target, memberId, role) => void run(() => changeRole(target, memberId, role)),
              }}
              empty="They hold nothing you may list."
            />
          </section>
          {attachAt !== null && (
            <section className="access-person-section" aria-label="Attach a policy to them">
              <h4 className="access-person-heading">Attach a policy</h4>
              {attachable.length > 1 && (
                <label className="access-att-field">
                  <span>At</span>
                  <select
                    className="access-input"
                    aria-label="Attach at"
                    value={attachAt}
                    onChange={(event) => setAttachPick(event.target.value)}
                  >
                    {attachable.map((level) => (
                      <option key={level} value={level}>
                        {levelLabel(level === PLATFORM ? null : level, names)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <AttachForm
                key={attachAt}
                api={api}
                // The platform's level is an attachment everywhere (no scope), as on People & roles.
                scope={attachAt === PLATFORM ? null : attachAt}
                principals={[]}
                principalId={personId}
                principalKind="user"
                onAttached={() => void load()}
              />
            </section>
          )}
          <section className="access-person-section" aria-label="Groups">
            <h4 className="access-person-heading">Groups</h4>
            {loaded.groups.length === 0 ? (
              <p className="access-holding-empty">In no group you may see.</p>
            ) : (
              <ul className="access-person-groups">
                {loaded.groups.map(({ group }) => (
                  <li key={group.id} data-group-of={group.id}>
                    {open?.group ? (
                      <button
                        type="button"
                        className="access-holding-link"
                        onClick={() => open.group?.(group.id, principalLabel(group, group.id))}
                      >
                        {principalLabel(group, group.id)}
                      </button>
                    ) : (
                      principalLabel(group, group.id)
                    )}{' '}
                    <span className="access-people-sub">{levelLabel(group.owner_scope ?? PLATFORM, names)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
