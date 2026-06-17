'use client'

import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink, Loader2, X } from 'lucide-react'
import { fetchInstanceDetail, type InstanceDetail } from '@/lib/graph-query/client'
import { compactUri } from './format'

export interface InstanceDrawerProps {
  workspaceId: string
  /** The inspect history stack of individual IRIs; the last entry is the one shown. */
  trail: string[]
  /** Graphs to look in (the Composer's selected graphs); the first that has it wins. */
  graphs: string[]
  onClose: () => void
  /** Escalate to the full Individuals page for this individual. */
  onOpenFull: (uri: string) => void
  /** Inspect a related individual in place (relation click) — pushes onto the trail. */
  onNavigate: (uri: string) => void
  /** Truncate the trail to `index` (breadcrumb / back). */
  onJumpTo: (index: number) => void
}

const MIN_WIDTH = 300
const DEFAULT_WIDTH = 760
// Versioned key so the previous (narrower) default doesn't override the new one.
const STORAGE_KEY = 'composer-inspect-width-v2'

/**
 * Side panel that shows one individual's detail (data properties + relations). It sits as a
 * flex sibling of the table (pushing it, not overlaying), is resizable by dragging its left
 * edge, and keeps a breadcrumb trail so relation hops can be walked back. The grain query only
 * knows a row's URI, not its graph, so we resolve the graph by trying each selected graph.
 */
export function InstanceDrawer({
  workspaceId,
  trail,
  graphs,
  onClose,
  onOpenFull,
  onNavigate,
  onJumpTo,
}: InstanceDrawerProps) {
  const uri = trail[trail.length - 1]
  const canBack = trail.length > 1

  const [detail, setDetail] = useState<InstanceDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [width, setWidth] = useState(DEFAULT_WIDTH)

  // Restore / persist the panel width (clamped to what fits, so it never crowds out the table).
  useEffect(() => {
    const max = Math.max(MIN_WIDTH, window.innerWidth - 420)
    const saved = Number(window.localStorage.getItem(STORAGE_KEY))
    const initial = saved && saved >= MIN_WIDTH ? saved : DEFAULT_WIDTH
    setWidth(Math.min(initial, max))
  }, [])
  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, String(width))
  }, [width])

  const startResize = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = width
    const max = Math.max(MIN_WIDTH, window.innerWidth - 420)
    const onMove = (ev: MouseEvent) => {
      setWidth(Math.min(Math.max(startWidth + (startX - ev.clientX), MIN_WIDTH), max))
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'
  }

  // Escape closes the panel — unless the user is typing in a field (search box, filter, …),
  // where Escape belongs to that control.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      const el = document.activeElement as HTMLElement | null
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)) {
        return
      }
      onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // A double-click anywhere outside the panel closes it — except on a results row, which
  // re-inspects that individual instead (its own dblclick handler owns that gesture).
  useEffect(() => {
    const onDocDblClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null
      if (!target) return
      if (target.closest('[data-testid="explore-instance-drawer"]')) return
      if (target.closest('[data-testid="explore-row"]')) return
      onClose()
    }
    document.addEventListener('dblclick', onDocDblClick)
    return () => document.removeEventListener('dblclick', onDocDblClick)
  }, [onClose])

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
      className="relative flex h-full shrink-0 flex-col border-l bg-background"
      style={{ width }}
      data-testid="explore-instance-drawer"
    >
      {/* Drag-to-resize handle on the left edge. */}
      <div
        onMouseDown={startResize}
        className="absolute -left-1 top-0 z-10 h-full w-2 cursor-col-resize hover:bg-workspace-accent/30"
        title="Drag to resize"
        data-testid="instance-drawer-resize"
      />

      <header className="border-b">
        <div className="flex items-start gap-1 px-3 py-2">
          {canBack && (
            <button
              onClick={() => onJumpTo(trail.length - 2)}
              className="mt-0.5 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Back"
              data-testid="instance-drawer-back"
            >
              <ChevronLeft size={14} />
            </button>
          )}
          <div className="min-w-0 flex-1">
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
        </div>

        {canBack && (
          <div
            className="flex items-center gap-0.5 overflow-x-auto border-t px-3 py-1 text-[10px] text-muted-foreground"
            data-testid="instance-drawer-breadcrumb"
          >
            {trail.map((u, i) => (
              <span key={`${u}:${i}`} className="flex shrink-0 items-center gap-0.5">
                {i > 0 && <ChevronRight size={9} className="opacity-40" />}
                {i < trail.length - 1 ? (
                  <button
                    onClick={() => onJumpTo(i)}
                    className="max-w-[100px] truncate hover:text-foreground hover:underline"
                    title={u}
                  >
                    {compactUri(u)}
                  </button>
                ) : (
                  <span className="max-w-[120px] truncate font-medium text-foreground" title={u}>
                    {compactUri(u)}
                  </span>
                )}
              </span>
            ))}
          </div>
        )}
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
