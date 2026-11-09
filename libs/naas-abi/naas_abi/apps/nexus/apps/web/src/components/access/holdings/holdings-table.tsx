'use client';

import { useState } from 'react';
import type { AttachmentView } from '@/lib/iam-admin/types';
import { actionsKey, ownerHref } from '../policies/policy-owners';
import {
  ROLE_LABELS,
  assignableRoles,
  roleChangeable,
  roleOfPolicy,
  type BuiltInRole,
  type RoleTarget,
} from '../roles/role-change';
import { ConfirmDetach } from './confirm-detach';
import { levelLabel, roleTargetOf, type HoldingRow } from './holdings-model';
import './holdings.css';

export type RoleRules = {
  /** The person as the membership routes of ``target`` name them (the member of that
   *  organization or workspace), or null when not known there: the role is then read-only. */
  memberAt: (target: RoleTarget) => string | null;
  /** Who is looking, as the members name them: nobody changes their own role. */
  selfId: string | null;
  change: (target: RoleTarget, memberId: string, role: BuiltInRole) => void;
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
          {rows.map(({ attachment: a, via, role, companion, broughtBy }) => {
            const name = a.policy_name ?? a.policy_id;
            const level = levelLabel(a.scope, names);
            const owner = a.policy_owner_scope;
            // An owner that could not be read (null) names nowhere to link to.
            const href = !role && !companion && owner != null && opens(owner) ? ownerHref(owner, a.policy_id) : null;
            const target = role ? roleTargetOf(a.scope) : null;
            const choices = target ? assignableRoles(target.level) : [];
            const at = actionsAt(a.scope);
            const memberId = roles && target ? roles.memberAt(target) : null;
            const changeable =
              !!roles &&
              !!target &&
              !!role &&
              !!memberId &&
              choices.length > 0 &&
              !!at['iam:AttachPolicy'] &&
              roleChangeable({ role, inherited: false, userId: memberId, selfId: roles.selfId });
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
                  {companion && <span className="access-holding-badge">comes with a role</span>}
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
                    // Why they hold it: the roles it comes with, each at its level.
                    <span data-brought-by="">
                      {broughtBy.length
                        ? `Comes with ${broughtBy
                            .map((b) => `${ROLE_LABELS[roleOfPolicy(b.policy_id)!]} at ${levelLabel(b.scope, names)}`)
                            .join(', ')}`
                        : 'Comes with a role at a workspace'}
                    </span>
                  ) : (
                    'Direct'
                  )}
                </td>
                <td className="access-holding-actions">
                  {changeable && target && role && memberId ? (
                    <select
                      className="access-input"
                      aria-label={`Role at ${level}`}
                      value={role}
                      onChange={(e) => roles!.change(target, memberId, e.target.value as BuiltInRole)}
                    >
                      {!choices.includes(role) && <option value={role}>{ROLE_LABELS[role]}</option>}
                      {choices.map((choice) => (
                        <option key={choice} value={choice}>
                          {ROLE_LABELS[choice]}
                        </option>
                      ))}
                    </select>
                  ) : detachable ? (
                    <ConfirmDetach
                      label={`Detach ${name} at ${level}`}
                      confirming={confirming === a.id}
                      onAsk={() => setConfirming(a.id)}
                      onKeep={() => setConfirming(null)}
                      onConfirm={() => {
                        setConfirming(null);
                        onDetach(a);
                      }}
                    />
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
