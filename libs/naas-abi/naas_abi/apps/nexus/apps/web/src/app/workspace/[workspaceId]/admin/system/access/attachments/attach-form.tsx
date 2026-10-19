'use client';

import { useEffect, useId, useState } from 'react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { AttachablePolicy } from '@/lib/iam-admin/types';
import './attachments.css';

export type PrincipalChoice = { id: string; label: string };

/**
 * Attach a policy to a principal at a scope. The policies offered are those IAM lets the
 * caller attach there (`attachable`). The principal is an IAM principal id, typed or picked
 * from the known ones; the scope is fixed (`scope`) or typed (`scopeEditable`: empty means
 * platform-wide, `abi:<org>:-` an org, `abi:<org>:<workspace>` a workspace).
 */
export function AttachForm({
  api,
  scope,
  scopeEditable = false,
  principals,
  onAttached,
}: {
  api: IamAdminApi;
  scope: string;
  scopeEditable?: boolean;
  principals: PrincipalChoice[];
  onAttached: () => void;
}) {
  const [scopeDraft, setScopeDraft] = useState(scope);
  const [committed, setCommitted] = useState(scope);
  const [policies, setPolicies] = useState<AttachablePolicy[] | null>(null);
  const [policyId, setPolicyId] = useState('');
  const [principalId, setPrincipalId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const listId = useId();

  useEffect(() => {
    setScopeDraft(scope);
    setCommitted(scope);
  }, [scope]);

  useEffect(() => {
    let cancelled = false;
    setPolicies(null);
    api
      .attachable(committed)
      .then((found) => {
        if (cancelled) return;
        setPolicies(found.items);
        setPolicyId((current) => (found.items.some((p) => p.id === current) ? current : (found.items[0]?.id ?? '')));
        setError(null);
      })
      .catch((e: unknown) => !cancelled && (setPolicies([]), setError(e instanceof Error ? e.message : String(e))));
    return () => {
      cancelled = true;
    };
  }, [api, committed]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.attach({
        policy_id: policyId,
        principal_id: principalId.trim(),
        scope: scopeEditable ? scopeDraft.trim() || null : scope,
      });
      setPrincipalId('');
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
      {scopeEditable && (
        <label className="access-att-field">
          <span>Scope (empty: platform-wide)</span>
          <input
            type="text"
            className="access-att-input"
            aria-label="Attach at scope"
            placeholder="abi:<org>:<workspace>, or abi:<org>:- for the org itself"
            value={scopeDraft}
            onChange={(event) => setScopeDraft(event.target.value)}
            onBlur={() => setCommitted(scopeDraft.trim())}
          />
        </label>
      )}
      <label className="access-att-field">
        <span>Policy</span>
        <select
          className="access-att-input"
          aria-label="Policy to attach"
          value={policyId}
          disabled={!policies?.length}
          onChange={(event) => setPolicyId(event.target.value)}
        >
          {(policies ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.id})
            </option>
          ))}
          {policies !== null && policies.length === 0 && <option value="">No policy can be attached here</option>}
        </select>
      </label>
      <label className="access-att-field">
        <span>Principal (IAM id)</span>
        <input
          type="text"
          className="access-att-input"
          aria-label="Principal to attach to"
          list={listId}
          autoComplete="off"
          placeholder="usr_…, a group or a service account id"
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
      <button type="submit" className="access-att-button access-att-button-primary" disabled={busy || !policyId || !principalId.trim()}>
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
