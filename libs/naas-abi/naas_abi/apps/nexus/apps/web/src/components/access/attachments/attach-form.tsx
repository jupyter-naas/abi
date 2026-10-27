'use client';

import { useEffect, useId, useMemo, useState } from 'react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { AttachablePolicy, PrincipalKind } from '@/lib/iam-admin/types';
import { isRoleCompanion, principalKindOf, roleOfPolicy } from '../roles/role-change';
import './attachments.css';

export type PrincipalChoice = { id: string; label: string; kind?: PrincipalKind };

/** A user's built-in role is a membership (People & roles' role column, Members), never a bare
 *  attachment; a group or a service account takes one. What comes with a role (its feature and
 *  platform companions) is IAM's to attach, offered to nobody. A principal not among the known
 *  ones is told by its id. */
export function offeredTo(policy: AttachablePolicy, principal: PrincipalChoice | undefined): boolean {
  if (isRoleCompanion(policy.id)) return false;
  const kind = principal?.kind ?? (principal ? principalKindOf(principal.id) : 'user');
  return !(roleOfPolicy(policy.id) && kind === 'user');
}

/**
 * Attach a policy to a principal at a scope (null: platform-wide). The policies offered are
 * those IAM lets the caller attach there (`attachable`). The principal is picked from
 * ``principals`` or typed as an IAM id; with ``principalId`` it is fixed (a group's page).
 */
export function AttachForm({
  api,
  scope,
  principals,
  principalId: fixed,
  onAttached,
}: {
  api: IamAdminApi;
  scope: string | null;
  principals: PrincipalChoice[];
  principalId?: string;
  onAttached: () => void;
}) {
  const [policies, setPolicies] = useState<AttachablePolicy[] | null>(null);
  const [policyId, setPolicyId] = useState('');
  const [principalId, setPrincipalId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const listId = useId();
  const target = (fixed ?? principalId).trim();
  const principal = useMemo<PrincipalChoice | undefined>(
    () =>
      principals.find((p) => p.id === target) ??
      (target ? { id: target, label: target, kind: fixed ? 'group' : principalKindOf(target) } : undefined),
    [principals, target, fixed],
  );

  useEffect(() => {
    let cancelled = false;
    setPolicies(null);
    api
      .attachable(scope ?? '')
      .then((found) => {
        if (cancelled) return;
        setPolicies(found.items);
        setError(null);
      })
      .catch((e: unknown) => !cancelled && (setPolicies([]), setError(e instanceof Error ? e.message : String(e))));
    return () => {
      cancelled = true;
    };
  }, [api, scope]);

  const offered = useMemo(() => (policies ?? []).filter((p) => offeredTo(p, principal)), [policies, principal]);
  const chosen = offered.some((p) => p.id === policyId) ? policyId : (offered[0]?.id ?? '');

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.attach({ policy_id: chosen, principal_id: target, scope });
      if (!fixed) setPrincipalId('');
      onAttached();
    } catch (e) {
      setError(e instanceof IamAdminError || e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="access-att-form"
      aria-label="Attach a policy"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label className="access-att-field">
        <span>Policy</span>
        <select
          className="access-att-input"
          aria-label="Policy to attach"
          value={chosen}
          disabled={!offered.length}
          onChange={(event) => setPolicyId(event.target.value)}
        >
          {offered.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.id})
            </option>
          ))}
          {policies !== null && offered.length === 0 && <option value="">No policy can be attached here</option>}
        </select>
      </label>
      {!fixed && (
        <label className="access-att-field">
          <span>To</span>
          <input
            type="text"
            className="access-att-input"
            aria-label="Principal to attach to"
            list={listId}
            autoComplete="off"
            placeholder="A person, a group or a service account id"
            value={principalId}
            onChange={(event) => setPrincipalId(event.target.value)}
          />
          <datalist id={listId}>
            {principals.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </datalist>
        </label>
      )}
      <button type="submit" className="access-att-button access-att-button-primary" disabled={busy || !chosen || !target}>
        Attach policy
      </button>
      {error && (
        <p className="access-att-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
