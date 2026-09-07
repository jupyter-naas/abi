'use client';

import { useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Database, Table2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useDatasetsStore, type DatasetInfo } from '@/stores/datasets';
import { useWorkspaceStore } from '@/stores/workspace';
import { datasetsTablePath } from './lib/datasets-route';
import './datasets.css';

function groupByNamespace(datasets: DatasetInfo[]): [string, DatasetInfo[]][] {
  const grouped = new Map<string, DatasetInfo[]>();
  for (const dataset of datasets) {
    const list = grouped.get(dataset.namespace) ?? [];
    list.push(dataset);
    grouped.set(dataset.namespace, list);
  }
  return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export default function DatasetsCatalog() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { datasets, loading, error, fetchDatasets } = useDatasetsStore();

  useEffect(() => {
    void fetchDatasets(currentWorkspaceId);
  }, [currentWorkspaceId, fetchDatasets]);

  const groups = useMemo(() => groupByNamespace(datasets), [datasets]);

  if (isMobile) return null;

  return (
    <div className="datasets-root">
      <div className="datasets-header-gap">
        <Header title="Datasets" subtitle="SQL tables published by modules" />
      </div>
      <div className="datasets-body">
        {error ? <p className="datasets-banner datasets-banner--error">{error}</p> : null}
        {loading && datasets.length === 0 ? (
          <p className="datasets-empty">Loading tables…</p>
        ) : groups.length === 0 ? (
          <div className="datasets-empty">
            <Database size={20} />
            <h3>No datasets yet</h3>
            <p>
              Modules such as Clockify, Gmail, Calendar, and GitHub publish tables here
              after their ingest jobs run.
            </p>
          </div>
        ) : (
          groups.map(([namespace, tables]) => (
            <section key={namespace} className="datasets-group">
              <h2 className="datasets-group__title">{namespace}</h2>
              <div className="datasets-group__grid">
                {tables.map((table) => (
                  <button
                    key={`${table.namespace}.${table.name}`}
                    type="button"
                    className="datasets-card"
                    onClick={() =>
                      router.push(
                        datasetsTablePath(currentWorkspaceId, table.namespace, table.name),
                      )
                    }
                  >
                    <Table2 size={16} />
                    <span className="datasets-card__name">{table.name}</span>
                    <span className="datasets-card__meta">
                      {table.columns.length} columns
                      {table.partitions.length > 0
                        ? ` · ${table.partitions.length} partitions`
                        : ''}
                    </span>
                  </button>
                ))}
              </div>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
