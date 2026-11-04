'use client';

import { useState } from 'react';
import type { AttachmentView } from '@/lib/iam-admin/types';
import { actionsKey, ownerHref } from '../policies/policy-owners';
import {
  ROLE_LABELS,
  assignableRoles,
  roleChangeable,
  type BuiltInRole,
  type RoleTarget,
} from '../roles/role-change';
import { levelLabel, roleTargetOf, type HoldingRow } from './holdings-model';
import './holdings.css';

export type RoleRules = {
  /** The person, as the membership routes name them. */
  userId: string;
  /** Who is looking: nobody changes their own role. */
  selfId: string | null;
  change: (target: RoleTarget, role: BuiltInRole) => void;
};

type Props = {
  rows: HoldingRow[];
  /** Container → name, as the viewer may list them. */
  names: Record<string, string>;
  /** IAM's answer at a scope (`GET /access?scope=`): the detach, the role change, and
   *  whether the policy's owner page opens for the viewer. */
  actionsAt: (scope: string | null | undefined) => Record<string, boolean>;
  /** The page's own scope (`abi:` for the platform), whose rights are the page's. */
  here: string;
  onDetach: (attachment: AttachmentView) => void;
  onOpenGroup?: (id: string, label: string) => void;
  /** For a person's roles: changed as on Members. Without it, a role row is read-only. */
  roles?: RoleRules;
  empty: string;
};

/**
 * Roles, policies and group grants at every level: the policy (a link to it at its owner when
 * the viewer may manage something there), the level, whether it is direct or through a group,
 * and the detach or the role change, where IAM says the viewer may.
 */
export function HoldingsTable({ rows, names, actionsAt, here, onDetach, onOpenGroup, roles, empty }: Props) {
  const [confirming, setConfirming] = useState<string | null>(null);
  if (rows.length === 0) return <p className="access-holding-empty">{empty}</p>;

  const opens = (owner: string | null | undefined) =>
    actionsKey(owner) === here || Object.values(actionsAt(owner)).some(Boolean);

  return (
    <div className="access-table-wrap">
      <table className="access-table access-holding-table">
        <thead>
          <tr>
            <th>Role or policy</th>
            <th>Level</th>
            <th>Through</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {rows.map(({ attachment: a, via, role, companion }) => {
            const name = a.policy_name ?? a.policy_id;
            const level = levelLabel(a.scope, names);
            const owner = a.policy_owner_scope;
            const href = !role && !companion && owner !== undefined && opens(owner) ? ownerHref(owner, a.policy_id) : null;
            const target = role ? roleTargetOf(a.scope) : null;
            const choices = target ? assignableRoles(target.level) : [];
            const at = actionsAt(a.scope);
            const changeable =
              !!roles &&
              !!target &&
              !!role &&
              choices.length > 0 &&
              !!at['iam:AttachPolicy'] &&
              roleChangeable({ role, inherited: false, userId: roles.userId, selfId: roles.selfId });
            const detachable = !role && !companion && !via && !!at['iam:DetachPolicy'];
            return (
              <tr key={`${via?.id ?? ''}/${a.id}`} className="access-table-row" data-holding={a.policy_id} data-level={a.scope ?? ''} data-via={via?.id ?? ''}>
                <td>
                  {role ? (
                    <span data-role={role}>
                      {ROLE_LABELS[role]} <span className="access-holding-badge">role</span>
                    </span>
                  ) : href ? (
                    <a className="access-holding-link" href={href}>
                      {name}
                    </a>
                  ) : (
                    <span>{name}</span>
                  )}
                  {companion && <span className="access-holding-badge">with a role</span>}
                  {!role && <code className="access-holding-id">{a.policy_id}</code>}
                </td>
                <td title={a.scope ?? ''}>{level}</td>
                <td>
                  {via ? (
                    onOpenGroup ? (
                      <button type="button" className="access-holding-link" onClick={() => onOpenGroup(via.id, via.label)}>
                        {via.label}
                      </button>
                    ) : (
                      via.label
                    )
                  ) : companion ? (
                    'With the role'
                  ) : (
                    'Direct'
                  )}
                </td>
                <td className="access-holding-actions">
                  {changeable && target && role ? (
                    <select
                      className="access-input"
                      aria-label={`Role at ${level}`}
                      value={role}
                      onChange={(e) => roles!.change(target, e.target.value as BuiltInRole)}
                    >
                      {!choices.includes(role) && <option value={role}>{ROLE_LABELS[role]}</option>}
                      {choices.map((choice) => (
                        <option key={choice} value={choice}>
                          {ROLE_LABELS[choice]}
                        </option>
                      ))}
                    </select>
                  ) : detachable ? (
                    confirming === a.id ? (
                      <span>
                        <button
                          type="button"
                          className="access-button access-att-button-danger"
                          onClick={() => {
                            setConfirming(null);
                            onDetach(a);
                          }}
                        >
                          Confirm detach
                        </button>{' '}
                        <button type="button" className="access-button" onClick={() => setConfirming(null)}>
                          Keep
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="access-button"
                        aria-label={`Detach ${name} at ${level}`}
                        onClick={() => setConfirming(a.id)}
                      >
                        Detach
                      </button>
                    )
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
