'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ScopeHit } from '@/lib/search-scopes';
import { searchHref } from '@/lib/search-topics';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { TopicAvatar } from './topic-avatar';

/** Hits of any scope: one row shape, opened the way their feature opens them. */
export function ScopeHits({ workspaceId, hits, compact = false }: { workspaceId: string; hits: ScopeHit[]; compact?: boolean }) {
  return (
    <ul className="space-y-1.5">
      {hits.map(hit => <li key={hit.id}><HitRow workspaceId={workspaceId} hit={hit} compact={compact} /></li>)}
    </ul>
  );
}

function HitRow({ workspaceId, hit, compact }: { workspaceId: string; hit: ScopeHit; compact: boolean }) {
  const router = useRouter();
  const setStarredNavigation = useFilesStore(s => s.setStarredNavigation);
  const setActiveSource = useFilesStore(s => s.setActiveSource);
  const setActivePanelSection = useWorkspaceStore(s => s.setActivePanelSection);

  const body = (
    <>
      <TopicAvatar label={hit.title} image={hit.image} size={compact ? 32 : 40} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1 truncate text-sm font-medium">
          <span className="truncate">{hit.title}</span>
          {hit.action?.kind === 'external' && <ExternalLink size={11} className="flex-shrink-0 text-muted-foreground" />}
        </div>
        {hit.subtitle && <div className="truncate text-xs text-muted-foreground">{hit.subtitle}</div>}
        {hit.snippet && !compact && <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{hit.snippet}</p>}
      </div>
    </>
  );
  const row = cn('flex w-full gap-3 rounded-lg border bg-card text-left transition-colors', compact ? 'p-2' : 'p-3',
    hit.action && 'hover:border-workspace-accent');

  const action = hit.action;
  if (!action) return <div className={row} title={hit.subtitle || undefined}>{body}</div>;
  if (action.kind === 'external') {
    return <a href={action.href} target="_blank" rel="noopener noreferrer" className={row}>{body}</a>;
  }
  if (action.kind === 'href') return <Link href={action.href} className={row}>{body}</Link>;
  if (action.kind === 'topic-item') {
    return <Link href={searchHref(workspaceId, { scope: action.topic, item: action.uri, tab: 'details' })} scroll={false} className={row}>{body}</Link>;
  }
  // Files open in the Files page, at their folder, the way quick-open does it.
  return (
    <button
      type="button"
      className={row}
      onClick={() => {
        const parent = action.path.includes('/') ? action.path.slice(0, action.path.lastIndexOf('/')) : '';
        setStarredNavigation(action.type === 'folder'
          ? { source: action.source, path: action.path }
          : { source: action.source, path: parent, previewPath: action.path });
        setActiveSource(action.source);
        setActivePanelSection('files');
        router.push(`/workspace/${encodeURIComponent(workspaceId)}/files`);
      }}
    >
      {body}
    </button>
  );
}
