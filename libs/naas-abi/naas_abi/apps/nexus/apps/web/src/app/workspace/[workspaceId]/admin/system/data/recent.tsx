'use client';

/** What super admins changed or revealed lately, across services. */
import { useEffect, useState } from 'react';
import { History } from 'lucide-react';
import type { DataApi, Failure } from './data-api';
import type { AuditEntry } from './data-types';
import { Avatar, EmptyState, Notice, RelativeTime, SkeletonRows, StatusPill } from './data-ui';
import { Modal } from './modal';
import { groupHistory } from './inspector';
import { viewFor } from './services/registry';

const VERBS: Record<string, string> = { create: 'created', replace: 'replaced', delete: 'deleted', reveal: 'revealed' };

export function RecentChanges({
  api,
  onOpen,
  onClose,
}: {
  api: DataApi;
  onOpen: (service: string, id: string | null) => void;
  onClose: () => void;
}) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  useEffect(() => {
    let cancelled = false;
    void api.recent().then((result) => {
      if (cancelled) return;
      if (result.ok) setEntries(result.data.entries);
      else setFailure(result);
    });
    return () => {
      cancelled = true;
    };
  }, [api]);
  const grouped = entries ? groupHistory(entries) : null;
  return (
    <Modal title="Recent changes" subtitle="Changes and reveals made from the System app" icon={<History size={18} />} size="lg" onClose={onClose}>
      {failure && <Notice tone="danger">{failure.reason}</Notice>}
      {!grouped && !failure && <SkeletonRows rows={5} />}
      {grouped && grouped.length === 0 && (
        <EmptyState icon={History} title="Nothing yet">
          Every change and reveal made in the Data tab shows up here.
        </EmptyState>
      )}
      {grouped && grouped.length > 0 && (
        <ol className="data-history data-history-wide">
          {grouped.map((e, i) => {
            const view = viewFor(e.service);
            const Icon = view.icon;
            return (
              <li key={`${e.at}-${i}`} className="data-history-item">
                <Avatar name={e.actor || e.actor_id} />
                <div className="data-history-body">
                  <p className="data-history-line">
                    <strong>{e.actor || e.actor_id}</strong> {VERBS[e.operation] ?? e.operation}{' '}
                    <button
                      type="button"
                      className="data-link"
                      onClick={() => onOpen(e.service, e.operation === 'delete' && e.outcome === 'succeeded' ? null : e.resource_id)}
                    >
                      {e.resource_id}
                    </button>
                    {e.outcome === 'failed' && <StatusPill tone="danger" label="failed" />}
                  </p>
                  <p className="data-history-meta">
                    <Icon size={12} aria-hidden="true" /> {view.label} · <RelativeTime iso={e.at} />
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Modal>
  );
}
