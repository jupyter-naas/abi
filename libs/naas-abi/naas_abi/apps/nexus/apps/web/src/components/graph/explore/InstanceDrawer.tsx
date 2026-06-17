'use client'

import { useEffect, useState } from 'react'
import { ExternalLink, Loader2, X } from 'lucide-react'
import { fetchInstanceDetail, type InstanceDetail } from '@/lib/graph-query/client'
import { compactUri } from './format'

export interface InstanceDrawerProps {
  workspaceId: string
  /** The individual to inspect. */
  uri: string
  /** Graphs to look in (the Composer's selected graphs); the first that has it wins. */
  graphs: string[]
  onClose: () => void
  /** Escalate to the full Individuals page for this individual. */
  onOpenFull: (uri: string) => void
  /** Inspect a related individual in place (relation click). */
  onNavigate: (uri: string) => void
}

/**
 * Slide-over panel that shows one individual's detail (data properties + relations) without
 * leaving the Composer table. The grain query only knows a row's URI, not which graph it lives
 * in, so we resolve the graph by trying each selected graph until one returns the entity.
 */
export function InstanceDrawer({ workspaceId, uri, graphs, onClose, onOpenFull, onNavigate }: InstanceDrawerProps) {
  const [detail, setDetail] = useState<InstanceDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [notFound, setNotFound] = useState(false)

  const graphsKey = graphs.join('|')
  useEffect(() => {
    const graphList = graphsKey ? graphsKey.split('|') : []
    if (!uri || graphList.length === 0 || !workspaceId) {
      setDetail(null)
      setNotFound(graphList.length === 0)
      return
    }
    let cancelled = false
    setLoading(true)
    setDetail(null)
    setNotFound(false)
    ;(async () => {
      for (const g of graphList) {
        try {
          const d = await fetchInstanceDetail({ workspaceId, graphUri: g, instanceUri: uri })
          if (cancelled) return
          const found = !!d.class_uri || d.data_properties.length > 0 || d.relations.length > 0
          if (found) {
            setDetail(d)
            setLoading(false)
            return
          }
        } catch {
          /* not in this graph — try the next */
        }
      }
      if (!cancelled) {
        setNotFound(true)
        setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [uri, graphsKey, workspaceId])

  return (
    <aside
      className="absolute inset-y-0 right-0 z-30 flex w-[380px] max-w-full flex-col border-l bg-background shadow-xl"
      data-testid="explore-instance-drawer"
    >
      <header className="flex items-start justify-between gap-2 border-b px-3 py-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold" title={detail?.label || uri}>
            {detail?.label || compactUri(uri)}
          </div>
          <div className="truncate text-[11px] text-muted-foreground" title={detail?.class_uri || ''}>
            {detail?.class_label || (detail?.class_uri ? compactUri(detail.class_uri) : 'Individual')}
          </div>
          <div className="truncate font-mono text-[10px] text-muted-foreground/70" title={uri}>
            {uri}
          </div>
        </div>
        <button onClick={onClose} className="rounded p-1 hover:bg-muted" title="Close" data-testid="instance-drawer-close">
          <X size={14} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-3 py-2 text-xs">
        {loading ? (
          <div className="flex items-center gap-2 py-6 text-muted-foreground">
            <Loader2 className="animate-spin" size={14} /> Loading…
          </div>
        ) : notFound || !detail ? (
          <p className="py-6 text-muted-foreground">No detail found for this individual in the selected graph(s).</p>
        ) : (
          <>
            <Section title="Properties">
              {detail.data_properties.length === 0 ? (
                <Empty />
              ) : (
                detail.data_properties.map((dp, i) => (
                  <div key={i} className="flex flex-col border-b py-1 last:border-0">
                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {dp.predicate_label || compactUri(dp.predicate_uri)}
                    </span>
                    <span className="break-words">{dp.value}</span>
                  </div>
                ))
              )}
            </Section>

            <Section title={`Relations (${detail.relations.length})`}>
              {detail.relations.length === 0 ? (
                <Empty />
              ) : (
                detail.relations.map((r, i) => (
                  <button
                    key={i}
                    onClick={() => onNavigate(r.other_uri)}
                    className="flex w-full items-center gap-1.5 border-b py-1 text-left last:border-0 hover:bg-muted"
                    title={`Inspect ${r.other_uri}`}
                  >
                    <span className="text-[10px] text-muted-foreground" title={r.role}>
                      {r.role === 'domain' ? '→' : '←'}
                    </span>
                    <span className="truncate text-muted-foreground">{r.predicate_label || compactUri(r.predicate_uri)}</span>
                    <span className="ml-auto max-w-[150px] truncate font-medium" title={r.other_uri}>
                      {r.other_label || compactUri(r.other_uri)}
                    </span>
                  </button>
                ))
              )}
            </Section>
          </>
        )}
      </div>

      <footer className="border-t px-3 py-2">
        <button
          onClick={() => onOpenFull(uri)}
          className="flex w-full items-center justify-center gap-1.5 rounded border px-2 py-1 text-xs hover:bg-muted"
          data-testid="instance-drawer-open-full"
        >
          <ExternalLink size={12} /> Open in Individuals view
        </button>
      </footer>
    </aside>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">{title}</div>
      {children}
    </div>
  )
}

function Empty() {
  return <p className="py-1 text-muted-foreground/60">None.</p>
}
