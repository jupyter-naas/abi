'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { AttachmentView } from '@/lib/iam-admin/types';
import type { AccessNavigation } from '../access-props';
import { principalLabel } from '../attachments/attachments-model';
import { holdingRows, levelLabel } from '../holdings/holdings-model';
import '../holdings/holdings.css';
import { isRoleCompanion, roleOfPolicy } from '../roles/role-change';
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
}: {
  api: IamAdminApi;
  policyId: string;
  /** The page's own scope (`abi:` for the platform), whose rights are the page's ``can``. */
  here: string;
  can: (action: string) => boolean;
  open?: AccessNavigation;
}) {
  const [items, setItems] = useState<AttachmentView[] | null>(null);
  const [refused, setRefused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems((await api.listAttachments({ policy_id: policyId })).items);
      setRefused(false);
    } catch (e) {
      setItems([]);
      if (e instanceof IamAdminError && e.status === 403) setRefused(true);
      else setError(message(e));
    }
  }, [api, policyId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Ordered from the top level down, as on a person's page.
  const rows = useMemo(() => holdingRows(items ?? [], []).map((r) => r.attachment), [items]);
  const scopes = useMemo(() => rows.map((a) => a.scope), [rows]);
  const names = useContainerNames(api, scopes);
  const actionsAt = useActionsAt(api, scopes, here, can);
  const membership = !!roleOfPolicy(policyId) || isRoleCompanion(policyId);

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
        <p className="access-holding-empty">
          {refused ? 'You may not list where it is attached.' : 'Attached nowhere you may list.'}
        </p>
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
                const kind = a.principal?.kind ?? 'user';
                const level = levelLabel(a.scope, names);
                const go = open ? () => (kind === 'group' ? open.group(a.principal_id, who) : open.person(a.principal_id, who)) : null;
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
                      {!membership &&
                        actionsAt(a.scope)['iam:DetachPolicy'] &&
                        (confirming === a.id ? (
                          <span>
                            <button
                              type="button"
                              className="access-policy-button access-policy-button-danger"
                              onClick={() => {
                                setConfirming(null);
                                void detach(a);
                              }}
                            >
                              Confirm detach
                            </button>{' '}
                            <button type="button" className="access-policy-button" onClick={() => setConfirming(null)}>
                              Keep
                            </button>
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="access-policy-button"
                            aria-label={`Detach from ${who} at ${level}`}
                            onClick={() => setConfirming(a.id)}
                          >
                            Detach
                          </button>
                        ))}
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
