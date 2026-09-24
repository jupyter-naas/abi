'use client';

import { useState } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown } from 'lucide-react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { graphMode } from '@/lib/graph-explorer';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { useGraphExplorerStore } from '@/stores/graph-explorer';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { useConfirm } from '@/components/ui/dialogs';

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
  const row =
    'flex cursor-default select-none items-center gap-2 px-3 py-1.5 text-xs outline-none ![border-radius:0] data-[highlighted]:bg-transparent data-[disabled]:opacity-50';
  const surface =
    'z-[300] min-w-[190px] border-0 bg-card p-1 text-foreground !shadow-none outline-none !ring-0 focus:!ring-0 focus-visible:!ring-0 ![border-radius:0]';
  const trigger =
    'flex items-center gap-1 border-0 bg-transparent px-2 py-1 text-xs shadow-none outline-none ring-0 ![border-radius:0] hover:bg-transparent focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0 active:bg-transparent data-[state=open]:bg-transparent data-[state=open]:shadow-none';
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
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-3">
      <nav className="flex items-center gap-1" aria-label="Knowledge Graph menus">
        <span className="mr-1 hidden text-xs font-semibold sm:inline">Knowledge Graph</span>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger className={trigger}>
            File <ChevronDown size={11} />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="start" sideOffset={5} className={surface}>
              <DropdownMenu.Item
                className={row}
                onSelect={() => router.push(`${root}/create-graph`)}
              >
                Create New Graph
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className={row}
                onSelect={() =>
                  router.push(
                    `${root}/create-individual${graphs[0] ? `?graph=${encodeURIComponent(graphs[0])}` : ''}`,
                  )
                }
              >
                Create New Instance
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item className={row} onSelect={() => router.push(`${root}/import`)}>
                Import Triples…
              </DropdownMenu.Item>
              <DropdownMenu.Item className={row} onSelect={() => router.push(`${root}/export`)}>
                Export Triples…
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item
                className={row}
                disabled={!editable || busy}
                onSelect={() =>
                  router.push(`${root}/create-graph?edit=${encodeURIComponent(selected!.uri)}`)
                }
              >
                Edit Graph…
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className={row}
                disabled={!editable || busy}
                onSelect={() => void remove('clear')}
              >
                Clear Graph…
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className={row}
                disabled={!editable || busy}
                onSelect={() => void remove('delete')}
              >
                Delete Graph…
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger className={trigger}>
            View <ChevronDown size={11} />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="start" sideOffset={5} className={surface}>
              <DropdownMenu.RadioGroup
                value={graphMode(path)}
                onValueChange={(mode) => router.push(`${root}/${mode}`)}
              >
                {['Explorer', 'Composer'].map((mode) => (
                  <DropdownMenu.RadioItem key={mode} value={mode.toLowerCase()} className={row}>
                    <span className="w-3">
                      <DropdownMenu.ItemIndicator>
                        <Check size={12} />
                      </DropdownMenu.ItemIndicator>
                    </span>
                    {mode}
                  </DropdownMenu.RadioItem>
                ))}
              </DropdownMenu.RadioGroup>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item className={row} onSelect={openNetwork}>
                Open Network
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className={row}
                onSelect={() =>
                  router.push(
                    `${root}/individuals${graphs[0] ? `?graph=${encodeURIComponent(graphs[0])}` : ''}`,
                  )
                }
              >
                Manage Individuals
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px bg-border" />
              <DropdownMenu.Item className={row} disabled={busy} onSelect={() => void refresh()}>
                {busy ? 'Refreshing…' : 'Refresh'}
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </nav>
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      )}
      {dialog}
    </div>
  );
}
