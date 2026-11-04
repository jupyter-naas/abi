'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { type IamAdminApi } from '@/lib/iam-admin/api';
import type { AttachmentView, PrincipalKind } from '@/lib/iam-admin/types';
import type { AccessNavigation } from '../access-props';
import { principalLabel } from '../attachments/attachments-model';
import { ConfirmDetach } from '../holdings/confirm-detach';
import { byLevel, levelLabel } from '../holdings/holdings-model';
import '../holdings/holdings.css';
import { isRoleCompanion, principalKindOf, roleOfPolicy } from '../roles/role-change';
import { useActionsAt, useContainerNames } from './policy-owners';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/**
 * Where a policy is attached and to whom, at every level IAM lets the caller list
 * (`GET /attachments?policy_id=`): each row opens the person's or the group's page, names the
 * level as the Owner column does, and offers the detach where IAM says the caller may there.
 * A role and what comes with one are memberships: never detached here.
 */
export function PolicyAttachments({
  api,
  policyId,
  here,
  can,
  open,
  nonce = 0,
}: {
  api: IamAdminApi;
  policyId: string;
  /** The page's own scope (`abi:` for the platform), whose rights are the page's ``can``. */
  here: string;
  can: (action: string) => boolean;
  open?: AccessNavigation;
  /** Bumped by the page's refresh button: read again, rights included. */
  nonce?: number;
}) {
  const [items, setItems] = useState<AttachmentView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      // Across levels IAM answers what the caller may list: an empty list, never a refusal.
      setItems((await api.listAttachments({ policy_id: policyId })).items);
    } catch (e) {
      setItems([]);
      setError(message(e));
    }
  }, [api, policyId]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  // Ordered from the top level down, as on a person's page.
  const rows = useMemo(() => [...(items ?? [])].sort(byLevel), [items]);
  const scopes = useMemo(() => rows.map((a) => a.scope), [rows]);
  const names = useContainerNames(api, scopes, nonce);
  const actionsAt = useActionsAt(api, scopes, here, can, nonce);
  // A role is a membership only for a user (changed as on Members); a group or a service
  // account holds it as a plain attachment, detached here like any other.
  const membership = (kind: PrincipalKind) => isRoleCompanion(policyId) || (!!roleOfPolicy(policyId) && kind === 'user');

  const detach = async (a: AttachmentView) => {
    try {
      await api.detach({ policy_id: a.policy_id, principal_id: a.principal_id, scope: a.scope });
      setError(null);
      await load();
    } catch (e) {
      setError(message(e));
    }
  };

  if (items === null) return null;
  return (
    <section className="access-policy-attachments" aria-label="Where it is attached">
      <h4 className="access-policy-subheading">Attached to</h4>
      {error && (
        <p className="access-policy-error" role="alert">
          {error}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="access-holding-empty">Attached nowhere you may list.</p>
      ) : (
        <div className="access-table-wrap">
          <table className="access-table access-holding-table">
            <thead>
              <tr>
                <th>Who</th>
                <th>Level</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => {
                const who = principalLabel(a.principal, a.principal_id);
                // A principal whose record could not be read is told by its id's prefix.
                const kind = a.principal?.kind ?? principalKindOf(a.principal_id);
                const level = levelLabel(a.scope, names);
                const target = kind === 'group' ? open?.group : open?.person;
                const go = target ? () => target(a.principal_id, who) : null;
                return (
                  <tr key={a.id} className="access-table-row" data-attached={a.principal_id} data-level={a.scope ?? ''}>
                    <td>
                      {go ? (
                        <button type="button" className="access-holding-link" onClick={go}>
                          {who}
                        </button>
                      ) : (
                        who
                      )}
                      {kind !== 'user' && <span className="access-holding-badge">{kind.replace('_', ' ')}</span>}
                    </td>
                    <td title={a.scope ?? ''}>{level}</td>
                    <td className="access-holding-actions">
                      {!membership(kind) && actionsAt(a.scope)['iam:DetachPolicy'] && (
                        <ConfirmDetach
                          label={`Detach from ${who} at ${level}`}
                          confirming={confirming === a.id}
                          onAsk={() => setConfirming(a.id)}
                          onKeep={() => setConfirming(null)}
                          onConfirm={() => {
                            setConfirming(null);
                            void detach(a);
                          }}
                        />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
