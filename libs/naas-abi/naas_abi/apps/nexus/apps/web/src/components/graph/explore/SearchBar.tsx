'use client'

import { useEffect, useRef, useState } from 'react'
import { Box, Loader2, Search, Table2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { searchEntities, type SearchHit } from '@/lib/graph-query/client'
import { compactUri } from './format'

export interface SearchBarProps {
  workspaceId: string
  /** Graphs to scope the search to. Empty ⇒ search every graph the workspace owns. */
  graphUris: string[]
  onPick: (hit: SearchHit) => void
}

const DEBOUNCE_MS = 300

/**
 * Google-like entity search for the Composer. Type a string; results (classes + individuals)
 * appear in a dropdown below. Picking one configures the grain (graph + class, and an instance
 * pin for individuals) — an alternative entry point to the explicit graph + class pickers.
 */
export function SearchBar({ workspaceId, graphUris, onPick }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hits, setHits] = useState<SearchHit[]>([])
  const [error, setError] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const token = useRef(0)
  // Index of the keyboard-highlighted result across the flat [classes…, individuals…] order.
  const [activeIndex, setActiveIndex] = useState(0)
  const activeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const graphsKey = graphUris.join('|')
  useEffect(() => {
    const q = query.trim()
    if (!q || !workspaceId) {
      setHits([])
      setActiveIndex(0)
      setError(null)
      setLoading(false)
      return
    }
    const my = ++token.current
    setLoading(true)
    const scope = graphsKey ? graphsKey.split('|') : undefined
    const handle = setTimeout(() => {
      searchEntities({ workspaceId, query: q, graphUris: scope, limit: 20 })
        .then((resp) => {
          if (my === token.current) {
            setHits(resp.results)
            setActiveIndex(0)
            setError(null)
          }
        })
        .catch((e) => {
          if (my === token.current) {
            setHits([])
            setError(e instanceof Error ? e.message : 'Search failed')
          }
        })
        .finally(() => {
          if (my === token.current) setLoading(false)
        })
    }, DEBOUNCE_MS)
    return () => clearTimeout(handle)
  }, [query, workspaceId, graphsKey])

  const pick = (hit: SearchHit) => {
    onPick(hit)
    setOpen(false)
    setQuery('')
    setHits([])
    setActiveIndex(0)
  }

  const classes = hits.filter((h) => h.kind === 'class')
  const individuals = hits.filter((h) => h.kind === 'individual')
  // Flat, visual-order list (classes then individuals) that the arrow keys walk through.
  const ordered = [...classes, ...individuals]

  // Keep the keyboard-highlighted row scrolled into view as it moves.
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  return (
    <div ref={ref} className="relative" data-testid="explore-search">
      <div className="flex items-center gap-2 rounded-md border bg-background px-2.5 py-1.5 focus-within:ring-1 focus-within:ring-primary">
        <Search size={14} className="shrink-0 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setOpen(true)
              setActiveIndex((i) => Math.min(i + 1, ordered.length - 1))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActiveIndex((i) => Math.max(i - 1, 0))
            } else if (e.key === 'Enter') {
              const hit = ordered[activeIndex]
              if (open && hit) {
                e.preventDefault()
                pick(hit)
              }
            } else if (e.key === 'Escape') {
              setOpen(false)
            }
          }}
          placeholder="Search the graph — find a class or an individual by name…"
          data-testid="explore-search-input"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        {loading && <Loader2 size={13} className="shrink-0 animate-spin text-muted-foreground" />}
        {query && !loading && (
          <button
            onClick={() => {
              setQuery('')
              setHits([])
            }}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            title="Clear"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {open && query.trim() && (
        <div
          className="absolute left-0 right-0 top-full z-40 mt-1 max-h-96 overflow-y-auto rounded-md border bg-background py-1 shadow-lg"
          data-testid="explore-search-results"
        >
          {error ? (
            <p className="px-3 py-2 text-xs text-destructive">{error}</p>
          ) : loading && hits.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Searching…</p>
          ) : hits.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">No matches</p>
          ) : (
            <>
              {classes.length > 0 && (
                <Group title="Classes">
                  {classes.map((h, i) => (
                    <ResultRow
                      key={`c:${h.uri}:${h.graph_uri}`}
                      hit={h}
                      active={activeIndex === i}
                      innerRef={activeIndex === i ? activeRef : undefined}
                      onHover={() => setActiveIndex(i)}
                      onPick={pick}
                      icon={<Table2 size={13} className="text-blue-500" />}
                    />
                  ))}
                </Group>
              )}
              {individuals.length > 0 && (
                <Group title="Individuals">
                  {individuals.map((h, i) => {
                    const idx = classes.length + i
                    return (
                      <ResultRow
                        key={`i:${h.uri}:${h.graph_uri}`}
                        hit={h}
                        active={activeIndex === idx}
                        innerRef={activeIndex === idx ? activeRef : undefined}
                        onHover={() => setActiveIndex(idx)}
                        onPick={pick}
                        icon={<Box size={13} className="text-muted-foreground" />}
                      />
                    )
                  })}
                </Group>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-1 last:mb-0">
      <div className="px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">{title}</div>
      {children}
    </div>
  )
}

function ResultRow({
  hit,
  onPick,
  icon,
  active,
  innerRef,
  onHover,
}: {
  hit: SearchHit
  onPick: (h: SearchHit) => void
  icon: React.ReactNode
  active: boolean
  innerRef?: React.Ref<HTMLButtonElement>
  onHover?: () => void
}) {
  return (
    <button
      ref={innerRef}
      onMouseEnter={onHover}
      onClick={() => onPick(hit)}
      data-testid={`explore-search-hit-${hit.kind}`}
      data-active={active || undefined}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left',
        active ? 'bg-muted' : 'hover:bg-muted',
      )}
      title={hit.uri}
    >
      <span className="shrink-0">{icon}</span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-xs font-medium">{hit.label || compactUri(hit.uri)}</span>
        <span className="truncate text-[10px] text-muted-foreground">
          {hit.kind === 'individual'
            ? hit.class_label
            : `${hit.instance_count.toLocaleString()} instances`}{' '}
          · {compactUri(hit.graph_uri)}
        </span>
      </span>
    </button>
  )
}
