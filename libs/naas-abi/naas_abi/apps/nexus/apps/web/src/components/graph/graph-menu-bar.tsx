'use client';

import { useState } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { graphMode } from '@/lib/graph-explorer';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { useGraphExplorerStore } from '@/stores/graph-explorer';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { useConfirm } from '@/components/ui/dialogs';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';

export function GraphMenuBar() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const path = usePathname();
  const router = useRouter();
  const query = useSearchParams();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { confirm, dialog } = useConfirm();
  const root = `/workspace/${workspaceId}/graph`;
  const graphs = query.getAll('graph');
  const catalogKey = JSON.stringify([workspaceId, [...new Set(graphs)].sort()]);
  const catalog = useGraphExplorerStore((s) => (s.key === catalogKey ? s.data?.graphs : undefined));
  const selected = graphs.length === 1 ? catalog?.find((g) => g.uri === graphs[0]) : undefined;
  const editable =
    selected && selected.can_write === true &&
    !['schema', 'nexus'].includes(selected.uri.split('/').pop() || '') &&
    !['schema', 'nexus'].includes(selected.id);
  async function refresh() {
    setBusy(true);
    setError('');
    try {
      await useKnowledgeGraphStore.getState().clearCache();
      window.dispatchEvent(new Event('graph-cache-refresh'));
      window.dispatchEvent(new Event('views-changed'));
    } catch {
      setError('Refresh failed. Please try again.');
    } finally {
      setBusy(false);
    }
  }
  async function remove(action: 'clear' | 'delete') {
    if (!selected || !editable) return;
    if (
      !(await confirm({
        title: `${action === 'clear' ? 'Clear' : 'Delete'} graph “${selected.label}”?`,
        description:
          action === 'clear'
            ? 'Remove all triples from this graph. The graph will remain. This cannot be undone.'
            : 'Remove this graph and all its triples. This cannot be undone.',
        confirmLabel: action === 'clear' ? 'Clear Graph' : 'Delete Graph',
        destructive: true,
      }))
    )
      return;
    setBusy(true);
    setError('');
    try {
      const response = await authFetch(`${getApiUrl()}/api/graph/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId, uri: selected.uri }),
      });
      if (!response.ok) throw new Error();
      useKnowledgeGraphStore.getState().setActiveSavedView(null);
      if (action === 'delete') {
        useKnowledgeGraphStore.getState().selectGraph(null);
        useKnowledgeGraphStore.getState().setVisibleGraphs([]);
      }
      router.push(`${root}/explorer`);
      window.dispatchEvent(new Event('graph-list-update'));
      window.dispatchEvent(new Event('graph-cache-refresh'));
    } catch {
      setError(`Could not ${action} the graph. Please try again.`);
    } finally {
      setBusy(false);
    }
  }
  function openNetwork() {
    const p = new URLSearchParams();
    if (graphs[0]) p.set('graph', graphs[0]);
    const cls = query.get('class');
    if (cls) p.set('class', cls);
    router.push(`${root}/network?${p}`);
  }
  const inGraph = graphs[0] ? `?graph=${encodeURIComponent(graphs[0])}` : '';
  const locked = !editable || busy;
  const fileItems: MenuEntry[] = [
    { id: 'create-graph', label: 'Create New Graph', onSelect: () => router.push(`${root}/create-graph`) },
    { id: 'create-individual', label: 'Create New Instance', onSelect: () => router.push(`${root}/create-individual${inGraph}`) },
    { id: 'sep-io', kind: 'separator' },
    { id: 'import', label: 'Import Triples…', onSelect: () => router.push(`${root}/import`) },
    { id: 'export', label: 'Export Triples…', onSelect: () => router.push(`${root}/export`) },
    { id: 'sep-graph', kind: 'separator' },
    { id: 'edit', label: 'Edit Graph…', disabled: locked, onSelect: () => router.push(`${root}/create-graph?edit=${encodeURIComponent(selected!.uri)}`) },
    { id: 'clear', label: 'Clear Graph…', disabled: locked, onSelect: () => void remove('clear') },
    { id: 'delete', label: 'Delete Graph…', disabled: locked, onSelect: () => void remove('delete') },
  ];
  const viewItems: MenuEntry[] = [
    ...['Explorer', 'Composer'].map((mode) => ({
      id: mode.toLowerCase(),
      label: mode,
      checked: graphMode(path) === mode.toLowerCase(),
      onSelect: () => router.push(`${root}/${mode.toLowerCase()}`),
    })),
    { id: 'sep-open', kind: 'separator' },
    { id: 'network', label: 'Open Network', onSelect: openNetwork },
    { id: 'individuals', label: 'Manage Individuals', onSelect: () => router.push(`${root}/individuals${inGraph}`) },
    { id: 'sep-refresh', kind: 'separator' },
    { id: 'refresh', label: busy ? 'Refreshing…' : 'Refresh', disabled: busy, onSelect: () => void refresh() },
  ];
  return (
    <>
      <MenuBar
        label="Knowledge Graph menus"
        title="Knowledge Graph"
        className="flex-wrap"
        trailing={error ? <span role="alert" className="ml-2 text-xs text-destructive">{error}</span> : null}
      >
        <Menu label="File" items={fileItems} />
        <Menu label="View" items={viewItems} />
      </MenuBar>
      {dialog}
    </>
  );
}
