'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowRight, Loader2, RotateCw } from 'lucide-react';
import { formatHitCount, type SearchScope } from '@/lib/search-scopes';
import { searchHref } from '@/lib/search-topics';
import { scopeRunKey, useSearchScopesStore } from '@/stores/search-scopes';
import { ScopeHits } from './scope-hits';
import { TopicIcon } from './topic-icon';

export const ALL_VIEW_LIMIT = 5;
export const SCOPE_VIEW_LIMIT = 50;

/** "All": the query in every scope switched on, a short group per scope. Without a query the page shows its landing instead. */
export function AllScopesView({ workspaceId, scopes, q, onScopes, highlight = q }: {
  workspaceId: string;
  scopes: SearchScope[];
  q: string;
  onScopes: number;
  /** The words to mark in the results; empty when the search box was cleared. */
  highlight?: string;
}) {
  const run = useSearchScopesStore(s => s.run);
  const runs = useSearchScopesStore(s => s.runs);
  const nonce = useSearchScopesStore(s => s.nonce);
  useEffect(() => {
    if (!q.trim()) return;
    for (const scope of scopes) void run(workspaceId, scope, q, ALL_VIEW_LIMIT);
  }, [workspaceId, scopes, q, run, nonce]);

  if (!onScopes) {
    return <Empty>Every scope is switched off. Switch some on in the sidebar.</Empty>;
  }
  const states = scopes.map(scope => ({ scope, state: runs[scopeRunKey(workspaceId, scope.id, q, ALL_VIEW_LIMIT)] }));
  const shown = states.filter(({ state }) => !state || state.status !== 'done' || (state.result?.hits.length ?? 0) > 0);
  const empty = states.filter(({ state }) => state?.status === 'done' && !state.result?.hits.length).map(({ scope }) => scope.label);
  const pending = states.some(({ state }) => !state || state.status === 'loading');

  return (
    <div className="space-y-6">
      {shown.map(({ scope, state }) => (
        <section key={scope.id} className="space-y-2" aria-labelledby={`scope-${scope.id}`}>
          <div className="flex items-center justify-between gap-2">
            <h3 id={`scope-${scope.id}`} className="flex items-center gap-2 text-sm font-semibold">
              <TopicIcon name={scope.icon} /> {scope.label}
              {state?.status === 'done' && state.result && (
                <span className="font-normal text-muted-foreground">({formatHitCount(state.result)})</span>
              )}
              {state?.status === 'loading' && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
            </h3>
            {state?.status === 'done' && (
              <Link href={searchHref(workspaceId, { scope: scope.id, q })} className="inline-flex items-center gap-1 text-xs text-workspace-accent hover:underline">
                {state.result?.hasMore ? 'See all' : 'Open'} <ArrowRight size={12} />
              </Link>
            )}
          </div>
          {state?.status === 'error' ? (
            <ScopeError message={state.error} onRetry={() => void run(workspaceId, scope, q, ALL_VIEW_LIMIT, true)} />
          ) : state?.result ? (
            <ScopeHits workspaceId={workspaceId} hits={state.result.hits} compact query={highlight} />
          ) : null}
        </section>
      ))}
      {!pending && shown.length === 0 && <Empty>Nothing matches &ldquo;{q}&rdquo; in the scopes switched on.</Empty>}
      {empty.length > 0 && <p className="text-xs text-muted-foreground">No match in {empty.join(', ')}.</p>}
    </div>
  );
}

/** One feature or web scope on its own: its full list. */
export function FeatureScopeView({ workspaceId, scope, q, highlight = q }: { workspaceId: string; scope: SearchScope; q: string; highlight?: string }) {
  const run = useSearchScopesStore(s => s.run);
  const nonce = useSearchScopesStore(s => s.nonce);
  const state = useSearchScopesStore(s => s.runs[scopeRunKey(workspaceId, scope.id, q, SCOPE_VIEW_LIMIT)]);
  useEffect(() => { void run(workspaceId, scope, q, SCOPE_VIEW_LIMIT); }, [workspaceId, scope, q, run, nonce]);

  if (!state || (state.status === 'loading' && !state.result)) {
    return <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status"><Loader2 size={14} className="animate-spin" /> Searching {scope.label.toLowerCase()}…</p>;
  }
  if (state.status === 'error') return <ScopeError message={state.error} onRetry={() => void run(workspaceId, scope, q, SCOPE_VIEW_LIMIT, true)} />;
  const result = state.result!;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span aria-live="polite">{formatHitCount(result)} {(result.total ?? result.hits.length) === 1 ? 'result' : 'results'}{q ? ` for “${q}”` : ''}</span>
        <button type="button" onClick={() => void run(workspaceId, scope, q, SCOPE_VIEW_LIMIT, true)} className="inline-flex items-center gap-1 hover:text-foreground">
          <RotateCw size={12} /> Refresh
        </button>
      </div>
      {result.note && <p className="text-xs text-muted-foreground">{result.note}</p>}
      {result.hits.length ? <ScopeHits workspaceId={workspaceId} hits={result.hits} query={highlight} /> : <Empty>No {scope.label.toLowerCase()} {q ? <>match &ldquo;{q}&rdquo;</> : 'found'}.</Empty>}
      {result.hasMore && <p className="text-xs text-muted-foreground">Showing the first {result.hits.length}. Refine the search to narrow it down.</p>}
    </div>
  );
}

function ScopeError({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-2 text-xs text-red-500">
      <span>{message || 'Search failed'}</span>
      <button type="button" onClick={onRetry} className="underline">Retry</button>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{children}</div>;
}
