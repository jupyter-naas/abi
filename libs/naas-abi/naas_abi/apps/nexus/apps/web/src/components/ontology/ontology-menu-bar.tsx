'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { ontologyApiQuery } from '@/lib/ontology-query';
import { useOntologyStore } from '@/stores/ontology';
import { browserRoute, viewRoute, termTabs, ontologyBrowser } from '@/lib/ontology-navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { dashboardRoute } from '@/lib/ontology-dashboard';
import { ONTOLOGY_SPACING, ontologySpacing, ontologySpacingRoute } from '@/lib/ontology-spacing';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';

export function OntologyMenuBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const spacing = ontologySpacing(searchParams?.toString() || '');
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const root = `/workspace/${workspaceId}/ontology`;
  function navigate(view: string) {
    const query = searchParams?.toString() || '';
    router.push(`${root}?${view === 'overview' ? dashboardRoute(query) : viewRoute(query, view)}`, { scroll: false });
  }
  function selectBrowser(mode: string) {
    router.push(`${root}?${browserRoute(searchParams?.toString() || '', mode)}`);
  }
  function filePage(page: string) {
    const params = new URLSearchParams();
    const path = ontologyBrowser(searchParams?.toString() || '') === 'dictionary' ? null : searchParams?.get('ontology');
    if (path) params.set('ontology', path);
    router.push(`${root}/${page}${params.size ? `?${params}` : ''}`);
  }
  const query = searchParams?.toString() || '';
  const dictionary = ontologyBrowser(query) === 'dictionary';
  const curved = searchParams?.get('connectors') === 'curved';
  function setConnectors(value: string) {
    const params = new URLSearchParams(query);
    params.set('connectors', value);
    router.replace(`${root}?${params}`, { scroll: false });
  }
  async function refresh() {
    setRefreshing(true); setRefreshError(null);
    try {
      const response = await authFetch(`${getApiUrl()}/api/ontology/cache/clear${ontologyApiQuery()}`, { method: 'POST' });
      if (!response.ok) throw new Error(`Refresh failed (${response.status}).`);
      useOntologyStore.setState(state => ({ graphRefreshTrigger: state.graphRefreshTrigger + 1 }));
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : 'Refresh failed. Try again.');
    } finally { setRefreshing(false); }
  }
  const fileItems: MenuEntry[] = [
    { id: 'new-class', label: 'New Class', disabled: true },
    { id: 'new-property', label: 'New Object Property', disabled: true },
    { id: 'no-create', kind: 'note', label: 'Creation is unavailable until changes can be saved to an ontology file.' },
    { id: 'sep-io', kind: 'separator' },
    { id: 'import', label: 'Import Ontology…', onSelect: () => filePage('import') },
    { id: 'export', label: 'Export Ontology…', onSelect: () => filePage('export') },
  ];
  const views = dictionary ? [['system', 'System'], ['details', 'Details'], ['network', 'Network'], ['overview', 'Dashboard']] : [['network', 'Network'], ['overview', 'Dashboard'], ...termTabs];
  const viewItems: MenuEntry[] = [
    { id: 'sidebar', kind: 'heading', label: 'Sidebar' },
    { id: 'files', label: 'Files', checked: !dictionary, onSelect: () => selectBrowser('files') },
    { id: 'dictionary', label: 'Dictionary', checked: dictionary, onSelect: () => selectBrowser('dictionary') },
    { id: 'sep-views', kind: 'separator' },
    ...views.map(([view, label]) => ({ id: `view-${view}`, label, onSelect: () => navigate(view) })),
    { id: 'sep-connectors', kind: 'separator' },
    { id: 'connectors', kind: 'heading', label: 'Connectors' },
    { id: 'orthogonal', label: 'Right angles', checked: !curved, onSelect: () => setConnectors('orthogonal') },
    { id: 'curved', label: 'Curves', checked: curved, onSelect: () => setConnectors('curved') },
    { id: 'sep-spacing', kind: 'separator' },
    {
      id: 'spacing', kind: 'submenu', label: 'Spacing', value: spacing.label,
      items: ONTOLOGY_SPACING.map(option => ({
        id: option.value, label: option.label, checked: option.value === spacing.value,
        onSelect: () => router.replace(`${root}?${ontologySpacingRoute(query, option.value)}`, { scroll: false }),
      })),
    },
    { id: 'sep-refresh', kind: 'separator' },
    { id: 'refresh', label: refreshing ? 'Refreshing…' : 'Refresh', disabled: refreshing, onSelect: () => void refresh() },
  ];
  return <MenuBar
    label="Ontology menus"
    title="Ontology"
    className="flex-wrap"
    trailing={refreshError && <span role="alert" className="ml-2 text-xs text-destructive">{refreshError}</span>}
  >
    <Menu label="File" items={fileItems} />
    <Menu label="View" items={viewItems} />
  </MenuBar>;
}
