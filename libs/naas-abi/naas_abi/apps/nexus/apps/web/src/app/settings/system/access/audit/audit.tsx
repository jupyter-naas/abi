'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AuditEntry } from '@/lib/iam-admin/types';
import type { AccessViewProps } from '../access-props';
import './audit.css';

/** The outcome of one change: its request, then whether it succeeded or failed. */
export function outcome(entry: AuditEntry): string {
  if (entry.phase === 'failed') return entry.error ? `failed (${entry.error})` : 'failed';
  if (entry.phase === 'succeeded') return 'succeeded';
  return 'requested';
}

/** Entries whose operation contains `operation` (case-insensitive). */
export function filterByOperation(entries: AuditEntry[], operation: string): AuditEntry[] {
  const needle = operation.trim().toLowerCase();
  return needle ? entries.filter((e) => e.operation.toLowerCase().includes(needle)) : entries;
}

/** Every change IAM made through this app, newest first. A change is on record before it happens. */
export function AuditView({ api, nonce }: AccessViewProps) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [operation, setOperation] = useState('');
  const [resource, setResource] = useState('');

  const load = useCallback(async () => {
    try {
      setEntries((await api.audit({ resource_id: resource.trim() || undefined, limit: 200 })).items);
      setError(null);
    } catch (e) {
      setError(e instanceof IamAdminError ? e.message : String(e));
    }
  }, [api, resource]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const shown = useMemo(() => filterByOperation(entries ?? [], operation), [entries, operation]);

  return (
    <div className="access-audit">
      <div className="access-audit-filters">
        <input className="system-input" aria-label="Operation" placeholder="Operation (attach, key…)" value={operation} onChange={(e) => setOperation(e.target.value)} />
        <input className="system-input system-input-grow" aria-label="Resource id" placeholder="Resource id (exact)" value={resource} onChange={(e) => setResource(e.target.value)} />
      </div>
      {error && <p className="system-source-note" role="alert">{error}</p>}
      {entries === null && !error && <p className="system-empty">Loading…</p>}
      {entries !== null && (
        <div className="system-table-wrap">
          <table className="system-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Operation</th>
                <th>Resource</th>
                <th>Detail</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((entry, i) => (
                <tr key={`${entry.at}-${i}`} className="system-table-row" data-phase={entry.phase}>
                  <td>{new Date(entry.at).toLocaleString()}</td>
                  <td>{entry.actor || entry.actor_id}</td>
                  <td className="system-mono">{entry.operation}</td>
                  <td className="system-mono">{entry.resource_id}</td>
                  <td>{entry.detail || '–'}</td>
                  <td className={entry.phase === 'failed' ? 'access-audit-failed' : undefined}>{outcome(entry)}</td>
                </tr>
              ))}
              {shown.length === 0 && (
                <tr>
                  <td colSpan={6} className="system-empty">No changes recorded.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
