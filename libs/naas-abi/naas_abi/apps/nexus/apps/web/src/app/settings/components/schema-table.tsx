'use client';

import { AlertCircle, KeyRound, Link2, Lock } from 'lucide-react';
import { authFetch } from '@/stores/auth';

/** One column, as `GET /api/admin/tables/{name}/schema` returns it. */
export interface TableColumn {
  name: string;
  type: string;
  nullable: boolean;
  default: string | null;
  primary_key: boolean;
  references: string | null;
  redacted: boolean;
}

export type SchemaState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; columns: TableColumn[] };

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
  } catch {
    // ignore parse errors
  }
  return fallback;
}

/** Loads a table's columns; never throws (errors come back as an error state). */
export async function fetchTableSchema(name: string): Promise<SchemaState> {
  const fallback = `Failed to load the schema of ${name}.`;
  try {
    const res = await authFetch(`/api/admin/tables/${encodeURIComponent(name)}/schema`);
    if (!res.ok) return { status: 'error', message: await readApiError(res, fallback) };
    const data: { columns: TableColumn[] } = await res.json();
    return { status: 'ready', columns: data.columns };
  } catch {
    return { status: 'error', message: fallback };
  }
}

/** Columns of a table: type, nullable, default, primary and foreign keys, masked. */
export function SchemaTable({ state }: { state: SchemaState | undefined }) {
  if (!state || state.status === 'loading') {
    return <div className="org-settings-loading">Loading schema...</div>;
  }
  if (state.status === 'error') {
    return (
      <div className="org-settings-users-alert" role="alert">
        <AlertCircle size={16} />
        <span>{state.message}</span>
      </div>
    );
  }
  return (
    <table className="org-settings-users-table platform-schema-table">
      <thead>
        <tr>
          <th>Column</th>
          <th>Type</th>
          <th>Nullable</th>
          <th>Default</th>
          <th>Keys</th>
        </tr>
      </thead>
      <tbody>
        {state.columns.map((column) => (
          <tr key={column.name}>
            <td>
              <span className="platform-schema-column">
                {column.name}
                {column.redacted && (
                  <span className="platform-schema-tag" title="Values are masked in the table view">
                    <Lock size={11} />
                    masked
                  </span>
                )}
              </span>
            </td>
            <td>{column.type}</td>
            <td>{column.nullable ? 'yes' : 'no'}</td>
            <td title={column.default ?? undefined}>{column.default ?? ''}</td>
            <td>
              <span className="platform-schema-keys">
                {column.primary_key && (
                  <span className="platform-schema-tag">
                    <KeyRound size={11} />
                    primary
                  </span>
                )}
                {column.references && (
                  <span className="platform-schema-tag">
                    <Link2 size={11} />
                    {column.references}
                  </span>
                )}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
