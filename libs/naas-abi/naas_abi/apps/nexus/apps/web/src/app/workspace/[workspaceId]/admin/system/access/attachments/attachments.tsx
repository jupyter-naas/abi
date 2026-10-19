'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { AttachmentView, PrincipalView } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import { AttachForm, type PrincipalChoice } from './attach-form';
import { principalLabel } from './attachments-model';
import { AttachmentTable } from './attachments-table';
import './attachments.css';

/** Every attachment the caller may list: filter by principal, policy or scope, attach a
 *  policy anywhere IAM lets the caller, detach. */
export function AttachmentsView({ api, can, nonce = 0 }: AccessViewProps) {
  const [items, setItems] = useState<AttachmentView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [principals, setPrincipals] = useState<PrincipalView[]>([]);
  const [principalFilter, setPrincipalFilter] = useState('');
  const [policyFilter, setPolicyFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');

  const load = useCallback(async () => {
    try {
      const found = await api.listAttachments({
        principal_id: principalFilter.trim() || undefined,
        policy_id: policyFilter.trim() || undefined,
        scope: scopeFilter.trim() || undefined,
      });
      setItems(found.items);
      setError(null);
    } catch (e) {
      setItems([]);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [api, principalFilter, policyFilter, scopeFilter]);

  useEffect(() => {
    void load();
    // `nonce` is the header's refresh; the filters reload on Apply, not on every key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce]);

  useEffect(() => {
    if (!can('iam:ListPrincipals')) return;
    api
      .listPrincipals()
      .then((page) => setPrincipals(page.items))
      .catch(() => setPrincipals([]));
  }, [api, can]);

  const choices = useMemo<PrincipalChoice[]>(
    () => principals.map((p) => ({ id: p.id, label: principalLabel(p, p.id) })),
    [principals],
  );

  const detach = async (attachment: AttachmentView) => {
    try {
      await api.detach({
        policy_id: attachment.policy_id,
        principal_id: attachment.principal_id,
        scope: attachment.scope,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="access-att-view">
      <form
        className="access-att-filters"
        aria-label="Filter attachments"
        onSubmit={(event) => {
          event.preventDefault();
          void load();
        }}
      >
        <input
          type="text"
          className="access-att-input"
          aria-label="Filter by principal id"
          placeholder="Principal id"
          value={principalFilter}
          onChange={(event) => setPrincipalFilter(event.target.value)}
        />
        <input
          type="text"
          className="access-att-input"
          aria-label="Filter by policy id"
          placeholder="Policy id"
          value={policyFilter}
          onChange={(event) => setPolicyFilter(event.target.value)}
        />
        <input
          type="text"
          className="access-att-input"
          aria-label="Filter by scope"
          placeholder="Scope, e.g. abi:acme:-"
          value={scopeFilter}
          onChange={(event) => setScopeFilter(event.target.value)}
        />
        <button type="submit" className="access-att-button">
          Apply
        </button>
      </form>
      {error && (
        <p className="access-att-error" role="alert">
          {error}
        </p>
      )}
      {items === null ? (
        <p className="access-att-muted">Loading…</p>
      ) : (
        <AttachmentTable items={items} canDetach={can('iam:DetachPolicy')} onDetach={(a) => void detach(a)} />
      )}
      {can('iam:AttachPolicy') && (
        <AttachForm api={api} scope="" scopeEditable principals={choices} onAttached={() => void load()} />
      )}
    </div>
  );
}
