'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import type { AttachmentView } from '@/lib/iam-admin/types';
import { useAuthStore } from '@/stores/auth';
import type { ScopeMember } from '../access-directory';
import type { AccessViewProps } from '../access-props';
import { AttachForm, type PrincipalChoice } from '../attachments/attach-form';
import {
  ROLE_LABELS,
  assignableRoles,
  changeMemberRole,
  roleChangeable,
  type BuiltInRole,
  type RoleTarget,
} from '../roles/role-change';
import { groupHolders, peopleAt, type PersonRow } from './people-model';
import './people.css';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

type Props = AccessViewProps & {
  /** Changes a member's role (tests pass a fake); the membership routes by default. */
  changeRole?: (target: RoleTarget, userId: string, role: BuiltInRole) => Promise<void>;
};

function roleTarget(scope: AccessViewProps['scope']): RoleTarget | null {
  if (scope.level === 'workspace' && scope.workspaceId) return { level: 'workspace', workspaceId: scope.workspaceId };
  if (scope.level === 'organization' && scope.organizationId) {
    return { level: 'organization', organizationId: scope.organizationId };
  }
  return null;
}

/**
 * Who holds which role or policy at the scope: directly, or through a group that holds
 * policies there. A role that comes from the organization is shown read-only. Roles change as
 * memberships (`changeMemberRole`, the code Members uses), other policies are attached and
 * detached here; IAM decides every call.
 */
export function PeopleView({ api, can, scope, directory, nonce = 0, changeRole = changeMemberRole }: Props) {
  const selfId = useAuthStore((s) => s.user?.id ?? null);
  const [attachments, setAttachments] = useState<AttachmentView[] | null>(null);
  const [members, setMembers] = useState<ScopeMember[]>([]);
  const [rows, setRows] = useState<PersonRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    try {
      const [found, people] = await Promise.all([
        api.listAttachments(scope.value ? { scope: scope.value } : {}),
        directory.members(scope).catch(() => [] as ScopeMember[]),
      ]);
      // At the platform, what is attached everywhere; an org's or a workspace's attachments are theirs.
      const here = found.items.filter((a) => a.scope === scope.value);
      const groups = await Promise.all(groupHolders(here).map((id) => api.getGroup(id).catch(() => null)));
      setAttachments(here);
      setMembers(people);
      setRows(peopleAt(here, people, groups.flatMap((g) => (g ? [g] : []))));
      setError(null);
    } catch (e) {
      setAttachments([]);
      setError(message(e));
    }
  }, [api, directory, scope]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const choices = useMemo<PrincipalChoice[]>(() => {
    const seen = new Map<string, PrincipalChoice>();
    for (const m of members) seen.set(m.userId, { id: m.userId, label: m.name || m.email || m.userId, kind: 'user' });
    for (const r of rows) if (!seen.has(r.id)) seen.set(r.id, { id: r.id, label: r.label, kind: r.kind });
    return [...seen.values()];
  }, [members, rows]);

  const target = roleTarget(scope);
  const roles = assignableRoles(scope.level);
  const mayAttach = can('iam:AttachPolicy');
  const mayDetach = can('iam:DetachPolicy');

  const run = async (call: () => Promise<unknown>) => {
    try {
      await call();
      setError(null);
      await load();
    } catch (e) {
      setError(message(e));
    }
  };

  if (attachments === null) {
    return error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>;
  }

  const query = filter.trim().toLowerCase();
  const shown = rows.filter((r) => !query || `${r.label} ${r.email} ${r.id}`.toLowerCase().includes(query));

  return (
    <div className="access-people">
      <div className="access-people-toolbar">
        <input
          type="search"
          className="access-input access-input-grow"
          aria-label="Filter people"
          placeholder="Filter by name, email or id"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>
      {error && <p className="access-source-note" role="alert">{error}</p>}
      <div className="access-table-wrap">
        <table className="access-table">
          <thead>
            <tr>
              <th>Who</th>
              <th>Role</th>
              <th>Policies here</th>
              <th>Through groups</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((person) => {
              const changeable =
                !!target &&
                mayAttach &&
                person.member &&
                roles.length > 0 &&
                roleChangeable({ role: person.role, inherited: person.inherited, userId: person.id, selfId });
              return (
                <tr key={person.id} className="access-table-row" data-person={person.id}>
                  <td>
                    <span className="access-people-name">{person.label}</span>
                    {person.kind !== 'user' && <span className="access-people-kind">{person.kind.replace('_', ' ')}</span>}
                    {person.email && person.email !== person.label && <span className="access-people-sub">{person.email}</span>}
                  </td>
                  <td>
                    {changeable && target ? (
                      <select
                        className="access-input"
                        aria-label={`Role of ${person.label}`}
                        value={person.role ?? ''}
                        onChange={(e) => void run(() => changeRole(target, person.id, e.target.value as BuiltInRole))}
                      >
                        {person.role === null && <option value="">No role</option>}
                        {roles.map((role) => (
                          <option key={role} value={role}>
                            {ROLE_LABELS[role]}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span data-role={person.role ?? ''}>
                        {person.role ? ROLE_LABELS[person.role] : '–'}
                        {person.inherited && (
                          <span
                            className="access-people-badge"
                            title="Organization owners and admins reach every workspace of the organization. Change it in the organization's settings."
                          >
                            from organization
                          </span>
                        )}
                      </span>
                    )}
                  </td>
                  <td>
                    <ul className="access-people-chips">
                      {person.direct.map((a) => (
                        <li key={a.id} className="access-people-chip" data-held={a.policy_id}>
                          {a.policy_name ?? a.policy_id}
                          {mayDetach &&
                            (confirming === a.id ? (
                              <>
                                <button
                                  type="button"
                                  className="access-button access-att-button-danger"
                                  onClick={() => {
                                    setConfirming(null);
                                    void run(() =>
                                      api.detach({ policy_id: a.policy_id, principal_id: a.principal_id, scope: a.scope }),
                                    );
                                  }}
                                >
                                  Confirm detach
                                </button>
                                <button type="button" className="access-button" onClick={() => setConfirming(null)}>
                                  Keep
                                </button>
                              </>
                            ) : (
                              <button
                                type="button"
                                className="access-people-chip-remove"
                                aria-label={`Detach ${a.policy_name ?? a.policy_id} from ${person.label}`}
                                onClick={() => setConfirming(a.id)}
                              >
                                <X size={12} />
                              </button>
                            ))}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td>
                    {person.viaGroups.map((g) => (
                      <p key={g.groupId} className="access-people-via" data-via={g.groupId}>
                        <strong>{g.groupLabel}</strong>: {g.policies.map((p) => p.name).join(', ')}
                      </p>
                    ))}
                  </td>
                </tr>
              );
            })}
            {shown.length === 0 && (
              <tr>
                <td colSpan={4} className="access-empty">
                  {query ? 'Nobody matches.' : 'Nobody holds a role or a policy here.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {mayAttach && <AttachForm api={api} scope={scope.value} principals={choices} onAttached={() => void load()} />}
    </div>
  );
}
