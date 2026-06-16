'use client'

import { useParams } from 'next/navigation'
import { Header } from '@/components/shell/header'
import { GraphSectionNav } from '@/components/graph/graph-section-nav'
import { ExploreWorkbench } from '@/components/graph/explore/ExploreWorkbench'

/**
 * Next-generation Explore: a backend-driven, Excel-like query workbench built on the
 * /api/graph/query, /columns and /facets endpoints (AUDIT.md). Runs alongside the legacy
 * /graph/explore page during the rework so the two can be compared before the swap.
 */
export default function ExploreNextPage() {
  const params = useParams()
  const workspaceId = typeof params.workspaceId === 'string' ? params.workspaceId : ''

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <GraphSectionNav workspaceId={workspaceId} active="explore" />
          <div className="min-h-0 flex-1 overflow-hidden">
            <ExploreWorkbench workspaceId={workspaceId} />
          </div>
        </div>
      </div>
    </div>
  )
}
