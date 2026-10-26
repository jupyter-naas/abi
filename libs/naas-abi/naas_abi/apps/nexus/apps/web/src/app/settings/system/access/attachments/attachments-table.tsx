'use client';

import { useState } from 'react';
import type { AttachmentView } from '@/lib/iam-admin/types';
import { principalLabel, scopeLabel } from './attachments-model';
import './attachments.css';

/** Attachments as a table; detaching asks first. */
export function AttachmentTable({
  items,
  canDetach,
  onDetach,
  showScope = true,
}: {
  items: AttachmentView[];
  canDetach: boolean;
  onDetach: (attachment: AttachmentView) => void;
  showScope?: boolean;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);
  if (items.length === 0) return <p className="access-att-muted">Nothing is attached here.</p>;
  return (
    <table className="access-att-table">
      <thead>
        <tr>
          <th>Policy</th>
          <th>Attached to</th>
          {showScope && <th>Scope</th>}
          <th aria-label="Actions" />
        </tr>
      </thead>
      <tbody>
        {items.map((a) => (
          <tr key={a.id} data-attachment={a.id}>
            <td>
              {a.policy_name ?? a.policy_id} <code className="access-att-id">{a.policy_id}</code>
            </td>
            <td>
              {principalLabel(a.principal, a.principal_id)}
              {a.principal && <span className="access-att-kind">{a.principal.kind.replace('_', ' ')}</span>}
              <code className="access-att-id">{a.principal_id}</code>
            </td>
            {showScope && <td title={a.scope ?? ''}>{scopeLabel(a.scope)}</td>}
            <td className="access-att-actions">
              {canDetach &&
                (confirming === a.id ? (
                  <span>
                    Detach?{' '}
                    <button
                      type="button"
                      className="access-att-button access-att-button-danger"
                      onClick={() => {
                        setConfirming(null);
                        onDetach(a);
                      }}
                    >
                      Confirm detach
                    </button>{' '}
                    <button type="button" className="access-att-button" onClick={() => setConfirming(null)}>
                      Keep
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    className="access-att-button"
                    aria-label={`Detach ${a.policy_name ?? a.policy_id} from ${principalLabel(a.principal, a.principal_id)}`}
                    onClick={() => setConfirming(a.id)}
                  >
                    Detach
                  </button>
                ))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
