'use client'

import { ChevronRight, Filter } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SpineNode } from '@/lib/graph-query/pipeline'
import { compactUri } from './format'

export interface BreadcrumbProps {
  spine: SpineNode[]
  onDrillTo: (index: number) => void
}

/** Shows the navigation spine (root › … › grain). Past segments are clickable to step back. */
export function Breadcrumb({ spine, onDrillTo }: BreadcrumbProps) {
  if (spine.length <= 1) return null
  const lastIndex = spine.length - 1
  return (
    <div className="flex flex-wrap items-center gap-1 text-xs" data-testid="explore-breadcrumb">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Showing</span>
      {spine.map((node, i) => {
        const label = node.classLabel || compactUri(node.classUri)
        const isGrain = i === lastIndex
        const filterCount = Object.keys(node.filters).length
        return (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={12} className="text-muted-foreground/50" />}
            <button
              onClick={() => onDrillTo(i)}
              disabled={isGrain}
              data-testid={`breadcrumb-${i}`}
              className={cn(
                'flex items-center gap-1 rounded px-1.5 py-0.5',
                isGrain
                  ? 'bg-workspace-accent/15 font-medium text-workspace-accent'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
              title={isGrain ? 'Current rows' : `Go back to ${label}`}
            >
              {node.via && i > 0 && (
                <span className="text-[10px] text-muted-foreground/70">{node.via.label ?? node.via.predicate}</span>
              )}
              <span>{label}</span>
              {filterCount > 0 && !isGrain && (
                <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground" title={`${filterCount} filter(s)`}>
                  <Filter size={9} />
                  {filterCount}
                </span>
              )}
            </button>
          </span>
        )
      })}
    </div>
  )
}
