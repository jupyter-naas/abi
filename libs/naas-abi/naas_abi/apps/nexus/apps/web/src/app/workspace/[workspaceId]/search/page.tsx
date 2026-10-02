'use client';

/**
 * Workspace search across scopes: SPARQL topics (People, Organizations…), the
 * Nexus features (Apps, Chats, Files, Ontology…) and the Web.
 *
 * Without a scope the page is "All": the query runs in every scope switched on
 * in the sidebar and each answers with a short group. A scope opens on its own
 * with `?scope=<id>`: a topic gets its results, detail and ontology views, a
 * feature its full list, Web the multi-source search. All view state is in the
 * URL. Scopes are listed in `lib/search-scopes.ts`, searched by
 * `lib/search-providers.ts`; topics are configured in Settings → Search.
 */
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { LayoutGrid, Search as SearchIcon, Settings2, X } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { WorkspaceMark, WorkspaceMarkFrame } from '@/components/shell/workspace-mark';
import { AllScopesView, FeatureScopeView } from '@/components/search/scope-views';
import { TopicIcon } from '@/components/search/topic-icon';
import { TopicScopeView } from '@/components/search/topic-scope-view';
import { useSearchScopes } from '@/components/search/use-search-scopes';
import { WebSearchPanel } from '@/components/search/web-search-panel';
import { cn } from '@/lib/utils';
import { readSearchRoute, resolveScope, searchHref, type SearchRoute } from '@/lib/search-topics';
import { useWorkspaceStore } from '@/stores/workspace';

const TYPE_DEBOUNCE_MS = 300;

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <Search />
    </Suspense>
  );
}

function Search() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const searchParams = useSearchParams();
  const route = useMemo(() => readSearchRoute(searchParams), [searchParams]);
  const { scopes, isOn, topics, canEdit, error: topicsError } = useSearchScopes(workspaceId);

  const activeId = resolveScope(scopes, route.scope);
  const active = scopes.find(s => s.id === activeId) || null;
  const topic = active?.kind === 'topic' ? topics.find(t => t.id === active.id) || null : null;
  const onScopes = useMemo(() => scopes.filter(isOn), [scopes, isOn]);

  const go = useCallback((next: Partial<SearchRoute>, mode: 'push' | 'replace' = 'push') => {
    const href = searchHref(workspaceId, { ...route, scope: activeId, ...next });
    if (mode === 'replace') router.replace(href, { scroll: false });
    else router.push(href, { scroll: false });
  }, [workspaceId, route, activeId, router]);

  // The box types freely; the URL (and so the query) follows after a pause.
  const [input, setInput] = useState(route.q);
  const typing = useRef(false);
  useEffect(() => { if (!typing.current) setInput(route.q); }, [route.q]);
  useEffect(() => {
    if (!typing.current) return;
    const id = setTimeout(() => { typing.current = false; go({ q: input.trim() }, 'replace'); }, TYPE_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [input, go]);

  const placeholder = active ? `Search ${active.label.toLowerCase()}…` : `Search ${onScopes.length} scopes…`;
  // Nothing asked yet: the landing, search box in the middle. The same form
  // moves to the top once there is a query, so typing never loses focus.
  const landing = !active && !route.q;

  return (
    <div className="flex h-full flex-col">
      <Header title="Search" subtitle={active?.description || 'People, organizations, apps, files, chats, ontology and more'} />

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className={cn(landing
          ? 'mx-auto flex min-h-full max-w-2xl flex-col items-center justify-center gap-6 pb-[10vh] text-center'
          : 'mx-auto max-w-6xl space-y-4')}
        >
          {landing && <LandingHero />}

          <form
            role="search"
            onSubmit={(e) => { e.preventDefault(); typing.current = false; go({ q: input.trim() }, 'replace'); }}
            className={cn('group flex items-center gap-3 rounded-xl border bg-card shadow-sm transition-[border-color,box-shadow]',
              // The accent is a CSS variable, not a Tailwind colour: arbitrary values carry it.
              'focus-within:border-[color:var(--workspace-accent,#22c55e)] focus-within:shadow-[0_0_0_3px_color-mix(in_srgb,var(--workspace-accent,#22c55e)_22%,transparent)]',
              landing ? 'w-full px-4 py-3.5' : 'p-3')}
          >
            <SearchIcon size={landing ? 20 : 18} className="text-muted-foreground transition-colors group-focus-within:text-[color:var(--workspace-accent,#22c55e)]" />
            <input
              type="search"
              value={input}
              autoFocus
              onChange={(e) => { typing.current = true; setInput(e.target.value); }}
              placeholder={placeholder}
              aria-label={placeholder}
              className={cn('min-w-0 flex-1 bg-transparent caret-[color:var(--workspace-accent,#22c55e)] outline-none focus-visible:ring-0 placeholder:text-muted-foreground', landing ? 'text-base' : 'text-sm')}
            />
            {input && (
              <button type="button" aria-label="Clear search" onClick={() => { typing.current = false; setInput(''); go({ q: '' }, 'replace'); }}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                <X size={16} />
              </button>
            )}
          </form>

          {landing ? (
            /* The scopes switched on in the sidebar, i.e. what a search here will cover; one click opens it. */
            <nav aria-label="Search scopes" className="flex flex-wrap items-center justify-center gap-2">
              {onScopes.map(scope => (
                <Link
                  key={scope.id}
                  href={searchHref(workspaceId, { scope: scope.id })}
                  title={scope.description}
                  className="inline-flex items-center gap-1.5 border bg-secondary px-3 py-1 text-sm text-foreground transition-colors hover:border-workspace-accent hover:bg-workspace-accent-10 hover:text-workspace-accent"
                >
                  <TopicIcon name={scope.icon} /> {scope.label}
                </Link>
              ))}
              {canEdit && (
                <Link href={`/workspace/${encodeURIComponent(workspaceId)}/settings/search`}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground hover:text-foreground">
                  <Settings2 size={12} /> Topics
                </Link>
              )}
            </nav>
          ) : (
            /* Same scopes as the sidebar, for narrow screens where it is hidden. */
            <nav aria-label="Search scopes" className="-mx-1 flex items-center gap-1.5 overflow-x-auto px-1 pb-1">
              <ScopeChip active={!active} href={searchHref(workspaceId, { q: route.q })}><LayoutGrid size={14} /> All</ScopeChip>
              {onScopes.map(scope => (
                <ScopeChip key={scope.id} active={scope.id === activeId} href={searchHref(workspaceId, { scope: scope.id, q: route.q })}>
                  <TopicIcon name={scope.icon} /> {scope.label}
                </ScopeChip>
              ))}
              {active && !isOn(active) && (
                <ScopeChip active href={searchHref(workspaceId, { scope: active.id, q: route.q })}><TopicIcon name={active.icon} /> {active.label}</ScopeChip>
              )}
              {canEdit && (
                <Link href={`/workspace/${encodeURIComponent(workspaceId)}/settings/search${topic ? `?topic=${encodeURIComponent(topic.id)}` : ''}`}
                  className="ml-auto inline-flex flex-shrink-0 items-center gap-1 px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">
                  <Settings2 size={14} /> Topics
                </Link>
              )}
            </nav>
          )}

          {topicsError && <div role="alert" className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">{topicsError}</div>}

          {landing ? null : !active ? (
            <AllScopesView workspaceId={workspaceId} scopes={onScopes} q={route.q} onScopes={onScopes.length} />
          ) : topic ? (
            <TopicScopeView
              workspaceId={workspaceId}
              topic={topic}
              route={route}
              canEdit={canEdit}
              onTab={(tab) => go({ tab })}
            />
          ) : active.kind === 'web' ? (
            <WebSearchPanel query={route.q} />
          ) : (
            <FeatureScopeView workspaceId={workspaceId} scope={active} q={route.q} />
          )}
        </div>
      </div>
    </div>
  );
}

/** The workspace's own mark and name, as on the workspace switcher. */
function LandingHero() {
  const workspace = useWorkspaceStore(state => state.getCurrentWorkspace());
  return (
    <div className="flex flex-col items-center gap-3">
      <WorkspaceMarkFrame
        className="h-20 w-20 rounded-2xl shadow-sm"
        backgroundColor={workspace?.theme?.logoUrl ? undefined : (workspace?.theme?.primaryColor || '#22c55e')}
      >
        <WorkspaceMark
          name={workspace?.name}
          icon={workspace?.icon}
          logoUrl={workspace?.theme?.logoUrl}
          logoEmoji={workspace?.theme?.logoEmoji}
          letterClassName="text-3xl font-bold text-white"
        />
      </WorkspaceMarkFrame>
      <h1 className="text-3xl font-semibold tracking-tight">{workspace?.name || 'Search'}</h1>
      <p className="text-sm text-muted-foreground">Search people, organizations, apps, files, chats, the ontology and more.</p>
    </div>
  );
}

function ScopeChip({ active, href, children }: { active: boolean; href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'inline-flex flex-shrink-0 items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors',
        active ? 'bg-workspace-accent text-white' : 'bg-secondary hover:bg-secondary/80',
      )}
    >
      {children}
    </Link>
  );
}
