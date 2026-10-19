'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type { AttachmentView } from '@/lib/iam-admin/types';
import { AttachForm, type PrincipalChoice } from './attach-form';
import { principalLabel } from './attachments-model';
import { AttachmentTable } from './attachments-table';
import './attachments.css';

export type ScopeChoice = { value: string; label: string };

/**
 * The attachments at a few scopes the caller chooses between (an org and its workspaces):
 * who holds which policy there, attach and detach. IAM decides each call; `can` only decides
 * which controls are shown. ``principals`` are suggestions; every principal that already
 * holds something at the scope is suggested too.
 */
export function AttachmentsPanel({
  api,
  scopes,
  principals = [],
  can,
  onScopeChange,
}: {
  api: IamAdminApi;
  scopes: ScopeChoice[];
  principals?: PrincipalChoice[];
  can: (action: string) => boolean;
  /** Told the scope shown, now and whenever it changes (a page asks IAM what the caller may do there). */
  onScopeChange?: (scope: string) => void;
}) {
  const [index, setIndex] = useState(0);
  const scope = scopes[Math.min(index, scopes.length - 1)]?.value ?? '';
  const [items, setItems] = useState<AttachmentView[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (scope) onScopeChange?.(scope);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  const load = useCallback(async () => {
    try {
      const found = await api.listAttachments({ scope });
      setItems(found.items);
      setError(null);
    } catch (e) {
      setItems([]);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [api, scope]);

  useEffect(() => {
    setItems(null);
    void load();
  }, [load]);

  const known = useMemo<PrincipalChoice[]>(() => {
    const seen = new Map<string, string>(principals.map((p) => [p.id, p.label]));
    for (const a of items ?? []) {
      if (!seen.has(a.principal_id)) seen.set(a.principal_id, principalLabel(a.principal, a.principal_id));
    }
    return [...seen].map(([id, label]) => ({ id, label }));
  }, [principals, items]);

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
    <div className="access-att-panel">
      {scopes.length > 1 && (
        <label className="access-att-field">
          <span>Scope</span>
          <select
            className="access-att-input"
            aria-label="Scope"
            value={index}
            onChange={(event) => setIndex(Number(event.target.value))}
          >
            {scopes.map((s, i) => (
              <option key={s.value} value={i}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {error && (
        <p className="access-att-error" role="alert">
          {error}
        </p>
      )}
      {items === null ? (
        <p className="access-att-muted">Loading…</p>
      ) : (
        <AttachmentTable items={items} canDetach={can('iam:DetachPolicy')} onDetach={(a) => void detach(a)} showScope={false} />
      )}
      {can('iam:AttachPolicy') && scope && (
        <AttachForm api={api} scope={scope} principals={known} onAttached={() => void load()} />
      )}
    </div>
  );
}
