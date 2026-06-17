'use client'

import { useEffect, useRef, useState } from 'react'
import { Box, Loader2, Search, Table2, X } from 'lucide-react'
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
  }

  const classes = hits.filter((h) => h.kind === 'class')
  const individuals = hits.filter((h) => h.kind === 'individual')

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
                  {classes.map((h) => (
                    <ResultRow
                      key={`c:${h.uri}:${h.graph_uri}`}
                      hit={h}
                      onPick={pick}
                      icon={<Table2 size={13} className="text-blue-500" />}
                    />
                  ))}
                </Group>
              )}
              {individuals.length > 0 && (
                <Group title="Individuals">
                  {individuals.map((h) => (
                    <ResultRow
                      key={`i:${h.uri}:${h.graph_uri}`}
                      hit={h}
                      onPick={pick}
                      icon={<Box size={13} className="text-muted-foreground" />}
                    />
                  ))}
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
}: {
  hit: SearchHit
  onPick: (h: SearchHit) => void
  icon: React.ReactNode
}) {
  return (
    <button
      onClick={() => onPick(hit)}
      data-testid={`explore-search-hit-${hit.kind}`}
      className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
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
