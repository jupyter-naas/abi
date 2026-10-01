'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { LayoutGrid, Search, Settings2 } from 'lucide-react';
import { ALL_VIEW_LIMIT } from '@/components/search/scope-views';
import { TopicIcon } from '@/components/search/topic-icon';
import { useSearchScopes } from '@/components/search/use-search-scopes';
import { cn } from '@/lib/utils';
import { scopeGroups, WEB_SCOPE } from '@/lib/search-scopes';
import { readSearchRoute, resolveScope, searchHref } from '@/lib/search-topics';
import { useSearchStore } from '@/stores/search';
import { scopeRunKey, useSearchScopesStore } from '@/stores/search-scopes';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

/**
 * Search column: every scope the search can read — topics (People…), the
 * workspace features (Apps, Chats, Files, Ontology…) and Web — each with a
 * switch that includes it in the "All" view, and a link that opens it alone.
 * Counts are the current query's hits in the All view. Web's sources are
 * toggled here too once Web is on.
 */
export function SearchSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();
  const pathname = usePathname();
  const route = readSearchRoute(useSearchParams());
  const { scopes, isOn, setScopeOn, allowedEngines, canEdit } = useSearchScopes(currentWorkspaceId);
  const runs = useSearchScopesStore(s => s.runs);
  const webEngines = useSearchStore(s => s.sources).filter(s => allowedEngines.includes(s.id));
  const toggleSource = useSearchStore(s => s.toggleSource);
  const invalidate = useSearchScopesStore(s => s.invalidate);

  const onSearchPage = !!pathname?.endsWith('/search');
  const active = onSearchPage ? resolveScope(scopes, route.scope) : undefined;
  const href = (scope: string | null) => currentWorkspaceId ? searchHref(currentWorkspaceId, { scope, q: route.q }) : '#';
  const onCount = scopes.filter(isOn).length;

  const count = (scopeId: string): string | null => {
    if (!onSearchPage || !route.q.trim() || !currentWorkspaceId) return null;
    const run = runs[scopeRunKey(currentWorkspaceId, scopeId, route.q, ALL_VIEW_LIMIT)];
    if (run?.status !== 'done' || !run.result) return null;
    return `${run.result.hits.length}${run.result.hasMore ? '+' : ''}`;
  };

  return (
    <CollapsibleSection
      id="search"
      icon={<Search size={18} />}
      label="Search"
      description="Search people, organizations and more"
      href={getWorkspacePath(currentWorkspaceId, '/search')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <Link href={href(null)} aria-current={active === null ? 'page' : undefined}
        className={cn(rowClass(active === null), 'mb-1')}>
        <LayoutGrid size={14} className="flex-shrink-0" />
        <span className="flex-1 truncate">All</span>
        <span className="text-[10px] text-muted-foreground">{onCount}/{scopes.length} on</span>
      </Link>

      {scopeGroups(scopes).map(group => {
        const allOn = group.id === 'web' ? webEngines.every(e => e.enabled) : group.scopes.every(isOn);
        return (
          <div key={group.id} className="mb-2 space-y-0.5">
            <div className="flex items-center justify-between px-1 py-1 text-xs font-medium text-muted-foreground">
              <span>{group.label}</span>
              {(group.id === 'web' ? webEngines.length : group.scopes.length) > 1 && (
                <button type="button" className="text-[10px] hover:text-foreground"
                  onClick={() => {
                    if (group.id !== 'web') { group.scopes.forEach(scope => setScopeOn(scope.id, !allOn)); return; }
                    webEngines.filter(e => e.enabled === allOn).forEach(e => toggleSource(e.id));
                    invalidate(WEB_SCOPE);
                  }}>
                  {allOn ? 'None' : 'All'}
                </button>
              )}
            </div>
            {group.id === 'web' ? webEngines.map(engine => (
              // Web has no row of its own: its engines are the switches, its title opens it.
              <div key={engine.id} className={cn(rowClass(active === WEB_SCOPE), 'pr-1')}>
                <Link href={href(WEB_SCOPE)} title={engine.description}
                  className={cn('flex min-w-0 flex-1 items-center gap-2', !engine.enabled && 'text-muted-foreground')}>
                  <TopicIcon name={engine.icon} className="flex-shrink-0" />
                  <span className="flex-1 truncate">{engine.name}</span>
                </Link>
                <ScopeSwitch label={engine.name} on={engine.enabled} onChange={() => { toggleSource(engine.id); invalidate(WEB_SCOPE); }} />
              </div>
            )) : group.scopes.map(scope => {
              const on = isOn(scope);
              const hits = on ? count(scope.id) : null;
              return (
                <div key={scope.id}>
                  <div className={cn(rowClass(active === scope.id), 'pr-1')}>
                    <Link href={href(scope.id)} aria-current={active === scope.id ? 'page' : undefined} title={scope.description}
                      className={cn('flex min-w-0 flex-1 items-center gap-2', !on && 'text-muted-foreground')}>
                      <TopicIcon name={scope.icon} className="flex-shrink-0" />
                      <span className="flex-1 truncate">{scope.label}</span>
                      {hits !== null && <span className="text-[10px] text-muted-foreground">{hits}</span>}
                    </Link>
                    <ScopeSwitch label={scope.label} on={on} onChange={() => setScopeOn(scope.id, !on)} />
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}

      {canEdit && currentWorkspaceId && (
        <Link href={`/workspace/${encodeURIComponent(currentWorkspaceId)}/settings/search`}
          className="mt-1 flex items-center gap-2 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-workspace-accent-10 hover:text-foreground">
          <Settings2 size={12} /> Manage topics
        </Link>
      )}
    </CollapsibleSection>
  );
}

function rowClass(isActive: boolean) {
  return cn(
    'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left search-sidebar-list-row transition-colors hover:bg-workspace-accent-10',
    isActive ? 'bg-workspace-accent-15 text-workspace-accent' : 'text-foreground',
  );
}

/** Includes a scope in the "All" view. */
function ScopeSwitch({ label, on, onChange }: { label: string; on: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`Search ${label}`}
      title={on ? `Searched in All — click to leave ${label} out` : `Left out of All — click to search ${label}`}
      onClick={onChange}
      className={cn('relative h-4 w-7 flex-shrink-0 rounded-full transition-colors', on ? 'bg-workspace-accent' : 'bg-muted-foreground/30')}
    >
      <span className={cn('absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-all', on ? 'left-3.5' : 'left-0.5')} />
    </button>
  );
}
