'use client'

import { useParams, useSearchParams } from 'next/navigation'
import { Header } from '@/components/shell/header'
import { GraphDevBanner } from '@/components/graph/graph-dev-banner'
import { ExploreWorkbench } from '@/components/graph/explore/ExploreWorkbench'

/**
 * Composer: a backend-driven, Excel-like query workbench built on the /api/graph/query,
 * /columns, /facets and /search endpoints (AUDIT.md). Supersedes the legacy /graph/explore page
 * (whose tab is now hidden). A `?view_id=` param (set by the left "Composer" submenu) loads a
 * saved view on mount.
 */
export default function ExploreNextPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const workspaceId = typeof params.workspaceId === 'string' ? params.workspaceId : ''
  const viewIdToLoad = searchParams.get('view_id')

  return (
    <div className="flex h-full flex-col">
      <Header />
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
