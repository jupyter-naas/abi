'use client'

import { useMemo } from 'react'
import { Folder, Loader2, RefreshCw, Table2, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SavedView } from '@/lib/graph-query/client'

export interface ViewsSidebarProps {
  views: SavedView[]
  loading: boolean
  activeViewId: string | null
  onLoad: (view: SavedView) => void
  onDelete: (view: SavedView) => void
  onRefresh: () => void
}

interface FolderGroup {
  path: string
  views: SavedView[]
}

function groupByFolder(views: SavedView[]): FolderGroup[] {
  const byPath = new Map<string, SavedView[]>()
  for (const v of views) {
    const key = v.path ?? ''
    if (!byPath.has(key)) byPath.set(key, [])
    byPath.get(key)!.push(v)
  }
  return [...byPath.entries()]
    .map(([path, vs]) => ({ path, views: vs.sort((a, b) => (a.name ?? a.label).localeCompare(b.name ?? b.label)) }))
    .sort((a, b) => a.path.localeCompare(b.path))
}

export function ViewsSidebar({ views, loading, activeViewId, onLoad, onDelete, onRefresh }: ViewsSidebarProps) {
  const groups = useMemo(() => groupByFolder(views), [views])

  return (
    <aside className="flex w-60 flex-col border-r bg-muted/20" data-testid="explore-views-sidebar">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Saved views</span>
        <button onClick={onRefresh} className="rounded p-1 hover:bg-muted" title="Refresh" data-testid="views-refresh">
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {views.length === 0 && !loading ? (
          <p className="px-3 py-3 text-xs text-muted-foreground" data-testid="views-empty">
            No saved views yet. Build a query and click “Save view”.
          </p>
        ) : (
          groups.map((group) => (
            <div key={group.path || '(root)'} className="mb-1">
              {group.path && (
                <div className="flex items-center gap-1 px-3 py-1 text-[11px] font-medium text-muted-foreground">
                  <Folder size={11} />
                  <span className="truncate">{group.path}</span>
                </div>
              )}
              {group.views.map((view) => (
                <div
                  key={view.id}
                  className={cn(
                    'group flex items-center gap-1.5 px-3 py-1 text-xs hover:bg-muted',
                    activeViewId === view.id && 'bg-muted',
                  )}
                >
                  <button
                    onClick={() => onLoad(view)}
                    data-testid={`view-item-${view.id}`}
                    className="flex flex-1 items-center gap-1.5 truncate text-left"
                    title={view.name ?? view.label}
                  >
                    <Table2 size={12} className="shrink-0 text-muted-foreground" />
                    <span className="truncate">{view.name ?? view.label}</span>
                  </button>
                  <button
                    onClick={() => onDelete(view)}
                    data-testid={`view-delete-${view.id}`}
                    className="shrink-0 rounded p-0.5 text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100"
                    title="Delete view"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
