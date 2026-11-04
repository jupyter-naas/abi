'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AttachmentView, PrincipalView } from '@/lib/iam-admin/types';
import { useAuthStore } from '@/stores/auth';
import type { AccessViewProps } from '../access-props';
import { PLATFORM, ownerOf } from '../access-scope';
import { principalLabel } from '../attachments/attachments-model';
import { holdingRows, levelLabel, scopesOf, type GroupHoldings } from '../holdings/holdings-model';
import { HoldingsTable } from '../holdings/holdings-table';
import { useActionsAt, useContainerNames } from '../policies/policy-owners';
import { changeMemberRole, type BuiltInRole, type RoleTarget } from '../roles/role-change';
import './people.css';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const refused = (e: unknown) => e instanceof IamAdminError && e.status === 403;

type Props = AccessViewProps & {
  /** The person's IAM id. */
  personId: string;
  /** Their name as the page that opened this one shows it, until IAM's is read. */
  label?: string | null;
  /** Their account as the membership routes name it, when it is not their IAM id (an account
   *  linked from the old login); the IAM id otherwise. */
  memberId?: string | null;
  onClose: () => void;
  /** Changes a role (tests pass a fake); the membership routes by default. */
  changeRole?: (target: RoleTarget, userId: string, role: BuiltInRole) => Promise<void>;
};

type Loaded = {
  direct: AttachmentView[];
  groups: GroupHoldings[];
  /** IAM let the viewer list nothing this person holds. */
  refused: boolean;
  notices: string[];
  profile: PrincipalView | null;
};

/**
 * A person's page: every role, policy and group they hold, at every level IAM lets the viewer
 * list (`GET /attachments?principal_id=`, `GET /principals/{id}/groups` and each group's
 * attachments), whatever the level of the page it is opened from. Each row names its level as
 * the Owner column does, says whether it is direct or through which group, links to the policy
 * at its owner, and offers the detach (or, for a role, the change of role, as on Members) where
 * IAM says the viewer may. Nexus decides nothing here.
 */
export function PersonView({
  api,
  can,
  scope,
  nonce = 0,
  open,
  personId,
  label,
  memberId,
  onClose,
  changeRole = changeMemberRole,
}: Props) {
  const selfId = useAuthStore((s) => s.user?.id ?? null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const notices: string[] = [];
    const [direct, groups] = await Promise.all([
      api.listAttachments({ principal_id: personId }).then(
        (page) => ({ items: page.items, refused: false }),
        (e: unknown) => {
          if (!refused(e)) notices.push(`What they hold could not be read (${message(e)}).`);
          return { items: [] as AttachmentView[], refused: refused(e) };
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
    const held = await Promise.all(
      groups.map((group) =>
        api.listAttachments({ principal_id: group.id }).then(
          (page) => ({ group, attachments: page.items }),
          (e: unknown) => {
            if (!refused(e)) {
              notices.push(`What ${principalLabel(group, group.id)} gives could not be read (${message(e)}).`);
            }
            return { group, attachments: [] as AttachmentView[] };
          },
        ),
      ),
    );
    let profile = direct.items.find((a) => a.principal)?.principal ?? null;
    if (!profile) profile = await api.getPrincipal(personId).catch(() => null);
    setLoaded({ direct: direct.items, groups: held, refused: direct.refused && groups.length === 0, notices, profile });
  }, [api, personId]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const rows = useMemo(() => (loaded ? holdingRows(loaded.direct, loaded.groups) : []), [loaded]);
  const scopes = useMemo(
    () => [...scopesOf(rows), ...(loaded?.groups ?? []).map((g) => g.group.owner_scope ?? PLATFORM)],
    [rows, loaded],
  );
  const here = ownerOf(scope);
  const names = useContainerNames(api, scopes);
  const actionsAt = useActionsAt(api, scopes, here, can);

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
  const email = loaded?.profile?.email && loaded.profile.email !== name ? loaded.profile.email : null;

  return (
    <div className="access-person" data-person-page={personId}>
      <button type="button" className="access-person-back" onClick={onClose}>
        <ArrowLeft size={14} /> People &amp; roles
      </button>
      <header className="access-person-header">
        <h3 className="access-person-name">{name}</h3>
        {email && <span className="access-people-sub">{email}</span>}
        <code className="access-mono">{personId}</code>
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
              onOpenGroup={open ? (id, groupLabel) => open.group(id, groupLabel) : undefined}
              roles={{
                userId: memberId || personId,
                selfId,
                change: (target, role) => void run(() => changeRole(target, memberId || personId, role)),
              }}
              empty={
                loaded.refused
                  ? 'You may not list what this person holds.'
                  : 'They hold nothing you may list.'
              }
            />
          </section>
          <section className="access-person-section" aria-label="Groups">
            <h4 className="access-person-heading">Groups</h4>
            {loaded.groups.length === 0 ? (
              <p className="access-holding-empty">In no group you may see.</p>
            ) : (
              <ul className="access-person-groups">
                {loaded.groups.map(({ group }) => (
                  <li key={group.id} data-group-of={group.id}>
                    {open ? (
                      <button
                        type="button"
                        className="access-holding-link"
                        onClick={() => open.group(group.id, principalLabel(group, group.id))}
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
