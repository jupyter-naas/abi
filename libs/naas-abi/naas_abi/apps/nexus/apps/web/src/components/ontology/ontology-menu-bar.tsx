'use client';

import { useState } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { ontologyApiQuery } from '@/lib/ontology-query';
import { useOntologyStore } from '@/stores/ontology';
import { browserRoute, viewRoute, termTabs, ontologyBrowser } from '@/lib/ontology-navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { dashboardRoute } from '@/lib/ontology-dashboard';
import { ONTOLOGY_SPACING, ontologySpacing, ontologySpacingRoute } from '@/lib/ontology-spacing';

export function OntologyMenuBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const spacing = ontologySpacing(searchParams?.toString() || '');
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const root = `/workspace/${workspaceId}/ontology`;
  const row = 'flex cursor-default select-none items-center gap-2 rounded-sm px-3 py-1.5 text-xs outline-none data-[highlighted]:bg-muted data-[disabled]:opacity-50';
  const surface = 'z-[300] min-w-[190px] rounded-md border border-border bg-card p-1 text-foreground shadow-lg';
  const trigger = 'flex items-center gap-1 rounded px-2 py-1 text-xs hover:bg-muted data-[state=open]:bg-muted';
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
  return <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
    <nav className="flex shrink-0 items-center gap-1" aria-label="Ontology menus">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Ontology</span>
      <DropdownMenu.Root><DropdownMenu.Trigger className={trigger}>File <ChevronDown size={11} /></DropdownMenu.Trigger>
        <DropdownMenu.Portal><DropdownMenu.Content align="start" sideOffset={5} className={surface}>
          <DropdownMenu.Item className={row} disabled>New Class</DropdownMenu.Item>
          <DropdownMenu.Item className={row} disabled>New Object Property</DropdownMenu.Item>
          <p className="max-w-[220px] px-3 py-1 text-xs text-muted-foreground">Creation is unavailable until changes can be saved to an ontology file.</p>
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item className={row} onSelect={() => filePage('import')}>Import Ontology…</DropdownMenu.Item>
          <DropdownMenu.Item className={row} onSelect={() => filePage('export')}>Export Ontology…</DropdownMenu.Item>
        </DropdownMenu.Content></DropdownMenu.Portal>
      </DropdownMenu.Root>
      <DropdownMenu.Root><DropdownMenu.Trigger className={trigger}>View <ChevronDown size={11} /></DropdownMenu.Trigger>
        <DropdownMenu.Portal><DropdownMenu.Content align="start" sideOffset={5} className={surface}>
          <DropdownMenu.Label className="px-3 py-1 text-xs text-muted-foreground">Sidebar</DropdownMenu.Label>
          <DropdownMenu.RadioGroup value={ontologyBrowser(searchParams?.toString() || '') === 'dictionary' ? 'dictionary' : 'files'} onValueChange={selectBrowser}>
            {(['files', 'dictionary'] as const).map(mode => <DropdownMenu.RadioItem key={mode} value={mode} className={row}>
              <span className="flex w-3 items-center"><DropdownMenu.ItemIndicator><Check size={12} /></DropdownMenu.ItemIndicator></span>
              {mode === 'files' ? 'Files' : 'Dictionary'}
            </DropdownMenu.RadioItem>)}
          </DropdownMenu.RadioGroup>
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          {(ontologyBrowser(searchParams?.toString() || '') === 'dictionary' ? [['system', 'System'], ['details', 'Details'], ['network', 'Network'], ['overview', 'Dashboard']] : [['network', 'Network'], ['overview', 'Dashboard'], ...termTabs]).map(([view, label]) =>
            <DropdownMenu.Item key={view} className={row} onSelect={() => navigate(view)}>{label}</DropdownMenu.Item>)}
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Label className="px-3 py-1 text-xs text-muted-foreground">Connectors</DropdownMenu.Label>
          <DropdownMenu.RadioGroup value={searchParams?.get('connectors') === 'curved' ? 'curved' : 'orthogonal'} onValueChange={value => {
            const params = new URLSearchParams(searchParams?.toString() || '');
            params.set('connectors', value);
            router.replace(`${root}?${params}`, { scroll: false });
          }}>
            {([['orthogonal', 'Right angles'], ['curved', 'Curves']] as const).map(([value, label]) => <DropdownMenu.RadioItem key={value} value={value} className={row}>
              <span className="flex w-3 items-center"><DropdownMenu.ItemIndicator><Check size={12} /></DropdownMenu.ItemIndicator></span>{label}
            </DropdownMenu.RadioItem>)}
          </DropdownMenu.RadioGroup>
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Sub>
            <DropdownMenu.SubTrigger className={row}>
              Spacing <span className="ml-auto text-muted-foreground">{spacing.label}</span><ChevronRight size={12} />
            </DropdownMenu.SubTrigger>
            <DropdownMenu.Portal><DropdownMenu.SubContent sideOffset={4} collisionPadding={8} className={surface}>
              <DropdownMenu.RadioGroup value={spacing.value} onValueChange={value => {
                router.replace(`${root}?${ontologySpacingRoute(searchParams?.toString() || '', value)}`, { scroll: false });
              }}>
                {ONTOLOGY_SPACING.map(option => <DropdownMenu.RadioItem key={option.value} value={option.value} className={row}>
                  <span className="flex w-3 items-center"><DropdownMenu.ItemIndicator><Check size={12} /></DropdownMenu.ItemIndicator></span>{option.label}
                </DropdownMenu.RadioItem>)}
              </DropdownMenu.RadioGroup>
            </DropdownMenu.SubContent></DropdownMenu.Portal>
          </DropdownMenu.Sub>
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item className={row} disabled={refreshing} onSelect={() => {
            setRefreshing(true); setRefreshError(null);
            void (async () => {
              try {
                const response = await authFetch(`${getApiUrl()}/api/ontology/cache/clear${ontologyApiQuery()}`, { method: 'POST' });
                if (!response.ok) throw new Error(`Refresh failed (${response.status}).`);
                useOntologyStore.setState(state => ({ graphRefreshTrigger: state.graphRefreshTrigger + 1 }));
              } catch (error) {
                setRefreshError(error instanceof Error ? error.message : 'Refresh failed. Try again.');
              } finally { setRefreshing(false); }
            })();
          }}>{refreshing ? 'Refreshing…' : 'Refresh'}</DropdownMenu.Item>
        </DropdownMenu.Content></DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
    {refreshError && <span role="alert" className="text-xs text-destructive">{refreshError}</span>}
  </div>;
}
