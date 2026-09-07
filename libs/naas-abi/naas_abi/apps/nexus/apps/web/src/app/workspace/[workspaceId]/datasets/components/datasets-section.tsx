'use client';

import React, { useEffect } from 'react';
import { ChevronRight, Database, RefreshCw, Table2 } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useDatasetsStore, type DatasetInfo } from '@/stores/datasets';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { SidebarToolbar, SidebarToolbarButton } from '@/components/shell/sidebar/sidebar-toolbar';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { shellTokens } from '@/components/shell/tokens';
import {
  datasetsCatalogPath,
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

export function DatasetsNamespaceGroups({ dense }: { dense?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { namespace: activeNamespace, name: activeName } = parseDatasetsRoute(pathname);
  const {
    datasets,
    loading,
    error,
    expandedNamespaces,
    toggleNamespace,
    fetchDatasets,
  } = useDatasetsStore();

  useEffect(() => {
    void fetchDatasets(currentWorkspaceId);
  }, [currentWorkspaceId, fetchDatasets]);

  const groups = groupByNamespace(datasets);

  if (loading && datasets.length === 0) {
    return <p className="datasets-section-empty">Loading tables…</p>;
  }
  if (error) {
    return <p className="datasets-section-empty">{error}</p>;
  }
  if (groups.length === 0) {
    return <p className="datasets-section-empty">No datasets yet</p>;
  }

  return (
    <div className="datasets-section-list">
      {groups.map(([namespace, tables]) => {
        const isExpanded = expandedNamespaces.includes(namespace);
        return (
          <div key={namespace} className="datasets-namespace">
            <button
              type="button"
              onClick={() => toggleNamespace(namespace)}
              className={cn(
                'datasets-namespace__header',
                shellTokens.sidebar.sectionLabel,
              )}
            >
              <ChevronRight
                size={12}
                className={cn(
                  'datasets-namespace__chevron',
                  isExpanded && 'datasets-namespace__chevron--open',
                )}
              />
              <span className="datasets-namespace__label">{namespace}</span>
              <span className="datasets-namespace__count">{tables.length}</span>
            </button>
            {isExpanded && (
              <div className="datasets-namespace__items">
                {tables.map((table) => {
                  const active =
                    activeNamespace === table.namespace && activeName === table.name;
                  return (
                    <button
                      key={`${table.namespace}.${table.name}`}
                      type="button"
                      onClick={() =>
                        router.push(
                          datasetsTablePath(
                            currentWorkspaceId,
                            table.namespace,
                            table.name,
                          ),
                        )
                      }
                      className={cn(
                        'datasets-section-row',
                        shellTokens.sidebar.listRow,
                        active && 'datasets-section-row--active',
                        dense && 'datasets-section-row--dense',
                      )}
                    >
                      <Table2 size={14} className="datasets-section-row__icon" />
                      <span className="datasets-section-row__label">{table.name}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
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
  const fetchDatasets = useDatasetsStore((s) => s.fetchDatasets);

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
      <SidebarToolbar>
        <SidebarToolbarButton
          icon={<RefreshCw size={12} />}
          label="Refresh"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            void fetchDatasets(currentWorkspaceId);
          }}
        />
      </SidebarToolbar>
      <DatasetsNamespaceGroups dense={isMobilePanel} />
    </CollapsibleSection>
  );
}
