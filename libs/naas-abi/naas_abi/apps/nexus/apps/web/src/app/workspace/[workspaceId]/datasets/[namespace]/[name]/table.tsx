'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  useDatasetsStore,
  type DatasetInfo,
  type DatasetQueryResult,
} from '@/stores/datasets';
import { useWorkspaceStore } from '@/stores/workspace';
import './table.css';

function cellText(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function defaultSql(name: string): string {
  return `SELECT * FROM "${name.replace(/"/g, '""')}" LIMIT 100`;
}

export default function DatasetTable() {
  const params = useParams();
  const namespace = typeof params?.namespace === 'string' ? params.namespace : '';
  const name = typeof params?.name === 'string' ? params.name : '';
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const describe = useDatasetsStore((s) => s.describe);
  const preview = useDatasetsStore((s) => s.preview);
  const query = useDatasetsStore((s) => s.query);

  const [info, setInfo] = useState<DatasetInfo | null>(null);
  const [result, setResult] = useState<DatasetQueryResult | null>(null);
  const [sql, setSql] = useState('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!namespace || !name) return;
    setSql(defaultSql(name));
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const [described, previewed] = await Promise.all([
          describe(namespace, name, currentWorkspaceId),
          preview(namespace, name, currentWorkspaceId, 100),
        ]);
        setInfo(described);
        setResult(previewed);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dataset');
      } finally {
        setLoading(false);
      }
    })();
  }, [namespace, name, currentWorkspaceId, describe, preview]);

  const runQuery = async () => {
    if (!namespace) return;
    setRunning(true);
    setError(null);
    try {
      const queried = await query(namespace, sql, currentWorkspaceId);
      setResult(queried);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed');
    } finally {
      setRunning(false);
    }
  };

  const subtitle = useMemo(() => {
    if (!namespace || !name) return 'Dataset';
    return `${namespace}.${name}`;
  }, [namespace, name]);

  return (
    <div className="dataset-table-root">
      <div className="dataset-table-header-gap">
        <Header title="Datasets" subtitle={subtitle} />
      </div>
      <div className="dataset-table-body">
        {error ? <p className="dataset-table-banner dataset-table-banner--error">{error}</p> : null}

        {info ? (
          <section className="dataset-table-schema">
            <h2>Schema</h2>
            <p className="dataset-table-snapshot">snapshot {info.snapshot_id}</p>
            <table>
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Type</th>
                  <th>Partition</th>
                </tr>
              </thead>
              <tbody>
                {info.columns.map((column) => {
                  const partition = info.partitions.find((part) => part.column === column.name);
                  return (
                    <tr key={column.name}>
                      <td>{column.name}</td>
                      <td>{column.type}</td>
                      <td>{partition ? partition.transform : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        ) : null}

        <section className="dataset-table-query">
          <div className="dataset-table-query__bar">
            <h2>SQL</h2>
            <button
              type="button"
              className="dataset-table-run"
              onClick={() => void runQuery()}
              disabled={running || !sql.trim()}
            >
              {running ? 'Running…' : 'Run'}
            </button>
          </div>
          <textarea
            className="dataset-table-sql"
            value={sql}
            onChange={(event) => setSql(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                event.preventDefault();
                void runQuery();
              }
            }}
            spellCheck={false}
            rows={6}
          />
        </section>

        <section className="dataset-table-results">
          <h2>
            Results
            {result ? ` · ${result.rows.length} rows` : ''}
            {result?.truncated ? ' (truncated)' : ''}
          </h2>
          {loading && !result ? (
            <p className="dataset-table-muted">Loading preview…</p>
          ) : result && result.columns.length > 0 ? (
            <div className="dataset-table-scroll">
              <table>
                <thead>
                  <tr>
                    {result.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, index) => (
                    <tr key={index}>
                      {result.columns.map((column) => (
                        <td key={column}>{cellText(row[column])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="dataset-table-muted">No rows</p>
          )}
        </section>
      </div>
    </div>
  );
}
