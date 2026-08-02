'use client'

import { useParams, useSearchParams } from 'next/navigation'
import { Header } from '@/components/shell/header'
import { GraphDevBanner } from '@/components/graph/graph-dev-banner'
import { ExploreWorkbench } from '@/components/graph/explore/ExploreWorkbench'

/**
 * Composer: backend-driven Excel-like query workbench on /api/graph/query, /columns,
 * /facets, and /search (AUDIT.md). `/graph/explore` redirects here. A `?view_id=` param
 * from the Composer sidebar submenu loads a saved view on mount.
 */
export default function ExploreNextPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const workspaceId = typeof params.workspaceId === 'string' ? params.workspaceId : ''
  const viewIdToLoad = searchParams.get('view_id')

  return (
    <div className="flex h-full flex-col">
      <Header title="Explore Graph" />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <GraphDevBanner />
          <div className="min-h-0 flex-1 overflow-hidden">
            <ExploreWorkbench workspaceId={workspaceId} viewIdToLoad={viewIdToLoad} />
          </div>
        </div>
      </div>
    </div>
  )
}
