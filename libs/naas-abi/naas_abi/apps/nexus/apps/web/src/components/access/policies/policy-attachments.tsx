'use client';

import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { AttachablePolicy, AttachmentView, PrincipalKind } from '@/lib/iam-admin/types';
import type { AccessDirectory } from '../access-directory';
import type { AccessNavigation } from '../access-props';
import type { AccessScope } from '../access-scope';
import { offeredTo, type PrincipalChoice } from '../attachments/attach-form';
import { principalLabel } from '../attachments/attachments-model';
import { ConfirmDetach } from '../holdings/confirm-detach';
import { byLevel, levelLabel } from '../holdings/holdings-model';
import '../attachments/attachments.css';
import '../holdings/holdings.css';
import { isRoleCompanion, principalKindOf, roleOfPolicy } from '../roles/role-change';
import { useActionsAt, useContainerNames } from './policy-owners';

const message = (e: unknown) => (e instanceof IamAdminError || e instanceof Error ? e.message : String(e));

/**
 * Who holds a policy and at which level, at every level IAM lets the caller list
 * (`GET /attachments?policy_id=`): each row opens the person's or the group's page, names the
 * level as the Owner column does, and offers the detach where IAM says the caller may there.
 * A role and what comes with one are memberships: never detached here. With ``scope``, the
 * policy is attached here to someone of the scope (its members, its groups, at the platform its
 * service accounts, or an IAM id typed), where IAM lets the caller attach it there
 * (`GET /attachable-policies`), to whom the attach form would offer it: never a role to a
 * person (that is a membership, changed on Members), a service account's policy to a service
 * account only.
 */
export function PolicyAttachments({
  api,
  policyId,
  here,
  can,
  open,
  nonce = 0,
  scope,
  directory,
}: {
  api: IamAdminApi;
  policyId: string;
  /** The page's own scope (`abi:` for the platform), whose rights are the page's ``can``. */
  here: string;
  can: (action: string) => boolean;
  open?: AccessNavigation;
  /** Bumped by the page's refresh button: read again, rights included. */
  nonce?: number;
  /** The page's scope, where the policy is attached from here; without it, nothing is. */
  scope?: AccessScope;
  directory?: AccessDirectory;
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
    <section className="access-policy-attachments" aria-label="Who holds it">
      <h4 className="access-policy-subheading">Held by</h4>
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
      {scope && directory && can('iam:AttachPolicy') && (
        <AttachToPrincipal
          api={api}
          policyId={policyId}
          scope={scope}
          directory={directory}
          can={can}
          nonce={nonce}
          onAttached={() => void load()}
        />
      )}
    </section>
  );
}

/** Whom the policy may be attached to here: the scope's members, its groups, and at the
 *  platform its service accounts, as far as each can be read. */
async function principalsOf(
  api: IamAdminApi,
  scope: AccessScope,
  directory: AccessDirectory,
  can: (action: string) => boolean,
): Promise<PrincipalChoice[]> {
  const [members, groups, accounts] = await Promise.all([
    directory.members(scope).catch(() => []),
    can('iam:ListGroups') ? api.listGroups(scope.value ?? undefined).then((g) => g.items, () => []) : Promise.resolve([]),
    scope.level === 'platform' && can('iam:ListPrincipals')
      ? api.listPrincipals('service_account').then((p) => p.items, () => [])
      : Promise.resolve([]),
  ]);
  const seen = new Map<string, PrincipalChoice>();
  for (const m of members) {
    // A member's IAM id (an account linked from the old login has another id in Nexus).
    if (m.inherited) continue;
    const id = m.principalId ?? m.userId;
    seen.set(id, { id, label: m.name || m.email || id, kind: 'user' });
  }
  for (const p of [...groups, ...accounts]) seen.set(p.id, { id: p.id, label: principalLabel(p, p.id), kind: p.kind });
  return [...seen.values()];
}

/** The policy, attached at the page's scope to a principal picked or typed. */
function AttachToPrincipal({
  api,
  policyId,
  scope,
  directory,
  can,
  nonce,
  onAttached,
}: {
  api: IamAdminApi;
  policyId: string;
  scope: AccessScope;
  directory: AccessDirectory;
  can: (action: string) => boolean;
  nonce: number;
  onAttached: () => void;
}) {
  const [policy, setPolicy] = useState<AttachablePolicy | null | undefined>(undefined);
  const [choices, setChoices] = useState<PrincipalChoice[]>([]);
  const [principalId, setPrincipalId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const listId = useId();

  useEffect(() => {
    let cancelled = false;
    // Offered only where IAM lets the caller attach it: the policies attachable here.
    api
      .attachable(scope.value ?? '')
      .then((found) => !cancelled && setPolicy(found.items.find((p) => p.id === policyId) ?? null))
      .catch(() => !cancelled && setPolicy(null));
    void principalsOf(api, scope, directory, can).then((found) => !cancelled && setChoices(found));
    return () => {
      cancelled = true;
    };
  }, [api, policyId, scope, directory, can, nonce]);

  const offered = useMemo(() => (policy ? choices.filter((c) => offeredTo(policy, c)) : []), [policy, choices]);
  const target = principalId.trim();
  const typed = offered.find((c) => c.id === target) ?? (target ? { id: target, label: target, kind: principalKindOf(target) } : undefined);
  const allowed = !!policy && !!typed && offeredTo(policy, typed);

  if (!policy || isRoleCompanion(policyId)) return null;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.attach({ policy_id: policyId, principal_id: target, scope: scope.value });
      setPrincipalId('');
      onAttached();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="access-att-form"
      aria-label="Attach this policy"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label className="access-att-field">
        <span>Attach to</span>
        <input
          type="text"
          className="access-att-input"
          aria-label="Attach to"
          list={listId}
          autoComplete="off"
          placeholder={roleOfPolicy(policyId) ? 'A group or a service account id' : 'A person, a group or a service account id'}
          value={principalId}
          onChange={(event) => setPrincipalId(event.target.value)}
        />
        <datalist id={listId}>
          {offered.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </datalist>
      </label>
      <span className="access-att-scope">at {scope.label}</span>
      <button type="submit" className="access-att-button access-att-button-primary" disabled={busy || !allowed}>
        Attach
      </button>
      {target && typed && !offeredTo(policy, typed) && (
        <p className="access-att-error" role="status">
          {roleOfPolicy(policyId)
            ? 'A role is a membership: change it on Members.'
            : 'This policy is not attached to this kind of principal.'}
        </p>
      )}
      {error && (
        <p className="access-att-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
