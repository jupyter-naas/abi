'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { ChevronRight, Database, LayoutGrid, Search, Table2 } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useDatasetsStore, type DatasetInfo } from '@/stores/datasets';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { SearchPicker } from '@/components/shell/sidebar/search-picker';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { shellTokens } from '@/components/shell/tokens';
import {
  datasetsCatalogPath,
  datasetsNamespacePath,
  datasetsTablePath,
  parseDatasetsRoute,
} from '../lib/datasets-route';
import './datasets-components.css';

function groupByNamespace(datasets: DatasetInfo[]): [string, DatasetInfo[]][] {
  const grouped = new Map<string, DatasetInfo[]>();
  for (const dataset of datasets) {
    const list = grouped.get(dataset.namespace) ?? [];
    list.push(dataset);
    grouped.set(dataset.namespace, list);
  }
  return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
}

/** The tables kept by the namespace picker (none picked: every namespace) and the search
 *  (a table's name, its namespace or one of its columns). */
export function filterDatasets(datasets: DatasetInfo[], namespaces: readonly string[], query: string): DatasetInfo[] {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return datasets.filter((dataset) => {
    if (namespaces.length > 0 && !namespaces.includes(dataset.namespace)) return false;
    if (words.length === 0) return true;
    const text = [dataset.name, dataset.namespace, ...dataset.columns.map((column) => column.name)].join(' ').toLowerCase();
    return words.every((word) => text.includes(word));
  });
}

/** How the sidebar lists the tables: under their namespace, or all of them A–Z. */
export type DatasetsLayout = 'namespaces' | 'alphabetical';

/**
 * Datasets in the sidebar, as Ontology's: Dashboard (the catalog), a namespace picker and a
 * search, then the tables under their namespace (every one open unless folded) or A–Z. A
 * namespace's name opens its gallery; its chevron folds it.
 */
export function DatasetsNamespaceGroups({ dense }: { dense?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { namespace: activeNamespace, name: activeName } = parseDatasetsRoute(pathname);
  const { datasets, loading, error, collapsedNamespaces, toggleNamespace, fetchDatasets } = useDatasetsStore();
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [layout, setLayout] = useState<DatasetsLayout>('namespaces');

  useEffect(() => {
    void fetchDatasets(currentWorkspaceId);
  }, [currentWorkspaceId, fetchDatasets]);

  const allNamespaces = useMemo(() => groupByNamespace(datasets), [datasets]);
  const shown = filterDatasets(datasets, namespaces, query);
  const groups = groupByNamespace(shown);
  const searching = query.trim().length > 0;
  const onCatalog = !activeNamespace && !activeName;
  const namespaceLabel =
    namespaces.length === 0 ? 'All namespaces' : namespaces.length === 1 ? namespaces[0] : `${namespaces.length} namespaces selected`;

  const tableRow = (table: DatasetInfo, withNamespace: boolean) => {
    const active = activeNamespace === table.namespace && activeName === table.name;
    return (
      <button
        key={`${table.namespace}.${table.name}`}
        type="button"
        onClick={() => router.push(datasetsTablePath(currentWorkspaceId, table.namespace, table.name))}
        className={cn(
          'datasets-section-row',
          active && 'datasets-section-row--active',
          dense && 'datasets-section-row--dense',
        )}
        aria-current={active ? 'page' : undefined}
      >
        <Table2 size={14} className="datasets-section-row__icon" />
        <span className="datasets-section-row__label">{table.name}</span>
        {withNamespace && <span className="datasets-namespace__count">{table.namespace}</span>}
      </button>
    );
  };

  let body: React.ReactNode;
  if (loading && datasets.length === 0) body = <p className="datasets-section-empty">Loading tables…</p>;
  else if (error) body = <p className="datasets-section-empty">{error}</p>;
  else if (datasets.length === 0) body = <p className="datasets-section-empty">No datasets yet</p>;
  else if (shown.length === 0) body = <p className="datasets-section-empty">No table matches</p>;
  else if (layout === 'alphabetical')
    body = (
      <div className="datasets-section-list">
        {[...shown].sort((a, b) => a.name.localeCompare(b.name) || a.namespace.localeCompare(b.namespace)).map((table) => tableRow(table, true))}
      </div>
    );
  else
    body = (
      <div className="datasets-section-list">
        {groups.map(([namespace, tables]) => {
          // Open unless folded; a search opens every namespace it finds tables in.
          const isExpanded = searching || !collapsedNamespaces.includes(namespace);
          const galleryOpen = activeNamespace === namespace && !activeName;
          return (
            <div key={namespace} className="datasets-namespace">
              <div className={cn('datasets-namespace__header', shellTokens.sidebar.sectionLabel)}>
                <button
                  type="button"
                  aria-label={isExpanded ? `Fold ${namespace}` : `Open ${namespace}`}
                  aria-expanded={isExpanded}
                  onClick={() => toggleNamespace(namespace)}
                  className="datasets-namespace__toggle"
                >
                  <ChevronRight
                    size={12}
                    className={cn('datasets-namespace__chevron', isExpanded && 'datasets-namespace__chevron--open')}
                  />
                </button>
                <button
                  type="button"
                  data-namespace-gallery={namespace}
                  aria-current={galleryOpen ? 'page' : undefined}
                  onClick={() => router.push(datasetsNamespacePath(currentWorkspaceId, namespace))}
                  className={cn('datasets-namespace__label', galleryOpen && 'datasets-namespace__label--active')}
                >
                  {namespace}
                </button>
                <span className="datasets-namespace__count">{tables.length}</span>
              </div>
              {isExpanded && <div className="datasets-namespace__items">{tables.map((table) => tableRow(table, false))}</div>}
            </div>
          );
        })}
      </div>
    );

  return (
    <>
      <button
        type="button"
        className="shell-sidebar-home"
        aria-current={onCatalog ? 'page' : undefined}
        onClick={() => router.push(datasetsCatalogPath(currentWorkspaceId))}
      >
        <LayoutGrid size={14} aria-hidden="true" />
        <span>Dashboard</span>
      </button>
      {datasets.length > 0 && (
        <div className="datasets-section-filters space-y-2 px-2 pb-2 pt-2">
          <div className="search-picker-stack">
            <SearchPicker
              key={`namespaces:${currentWorkspaceId}`}
              items={allNamespaces.map(([namespace, tables]) => ({
                value: namespace,
                label: namespace,
                detail: `${tables.length} table${tables.length === 1 ? '' : 's'}`,
              }))}
              value={namespaces}
              onToggle={(namespace) =>
                setNamespaces((current) =>
                  current.includes(namespace) ? current.filter((value) => value !== namespace) : [...current, namespace]
                )
              }
              onClear={() => setNamespaces([])}
              loading={false}
              error={null}
              label={namespaceLabel}
              noun="namespaces"
              allLabel="All namespaces"
            />
          </div>
          <label className="relative block">
            <Search size={13} className="absolute left-2 top-2.5 text-muted-foreground" />
            <input
              aria-label="Search tables"
              placeholder="Search tables…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-md border bg-background py-2 pl-7 pr-2 text-xs"
            />
          </label>
          <div className="flex flex-wrap gap-1" aria-label="Sidebar view">
            {(['namespaces', 'alphabetical'] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={layout === value}
                onClick={() => setLayout(value)}
                className={cn(
                  'rounded-md px-2 py-1 text-xs',
                  layout === value ? 'bg-workspace-accent-10 text-workspace-accent' : 'text-muted-foreground hover:bg-muted'
                )}
              >
                {value === 'namespaces' ? 'Namespaces' : 'A–Z'}
              </button>
            ))}
          </div>
        </div>
      )}
      {body}
    </>
  );
}

export function DatasetsSection({
  collapsed,
  detailOnly,
}: {
  collapsed: boolean;
  detailOnly?: boolean;
}) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  const openCatalog = () => {
    router.push(datasetsCatalogPath(currentWorkspaceId));
  };

  return (
    <CollapsibleSection
      id="datasets"
      icon={<Database size={18} />}
      label="Datasets"
      description="SQL tables published by modules"
      href={getWorkspacePath(currentWorkspaceId, '/datasets')}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onNavigate={openCatalog}
    >
      <DatasetsNamespaceGroups dense={isMobilePanel} />
    </CollapsibleSection>
  );
}
