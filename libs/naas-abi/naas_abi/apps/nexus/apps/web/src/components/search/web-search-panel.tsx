'use client';

/**
 * The original multi-source search (web engines, conversations, files,
 * knowledge graph), kept as the "Web" tab of the search page. The query comes
 * from the page's search box; sources are toggled here or in the sidebar.
 */
import { useEffect, useState } from 'react';
import Image from 'next/image';
import {
  Search as SearchIcon,
  Filter,
  Globe,
  Shield,
  BookOpen,
  MessageSquare,
  FileCode,
  GitBranch,
  Network,
  Users,
  ExternalLink,
  ImageIcon,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { WEB_SCOPE } from '@/lib/search-scopes';
import { useSearchStore, WEB_ENGINE_IDS, type SearchSource, type SearchResult } from '@/stores/search';
import { useSearchScopesStore } from '@/stores/search-scopes';

// Icon map for sources
const iconMap: Record<string, LucideIcon> = {
  Globe,
  Shield,
  Search: SearchIcon,
  BookOpen,
  MessageSquare,
  FileCode,
  GitBranch,
  Network,
  Users,
};

// Source color map for visual distinction
const sourceColors: Record<string, string> = {
  wikipedia: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  duckduckgo: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
  google: 'bg-green-500/10 text-green-600 border-green-500/20',
  brave: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
  conversations: 'bg-pink-500/10 text-pink-600 border-pink-500/20',
  files: 'bg-cyan-500/10 text-cyan-600 border-cyan-500/20',
  'knowledge-graph': 'bg-indigo-500/10 text-indigo-600 border-indigo-500/20',
};

function SourceToggle({
  source,
  onToggle,
}: {
  source: SearchSource;
  onToggle: () => void;
}) {
  const IconComponent = iconMap[source.icon] || Globe;

  return (
    <button
      onClick={onToggle}
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
        source.enabled
          ? 'bg-workspace-accent text-white'
          : 'bg-secondary hover:bg-secondary/80'
      )}
      title={source.description}
    >
      <IconComponent size={14} />
      {source.name}
    </button>
  );
}

function ResultCard({ result, source, rank }: { result: SearchResult; source?: SearchSource; rank: number }) {
  const IconComponent = source ? iconMap[source.icon] || Globe : Globe;
  const imageUrl = result.metadata?.image as string | undefined;
  const colorClass = sourceColors[result.sourceId] || 'bg-muted text-muted-foreground';

  return (
    <a
      href={result.url || '#'}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-xl border bg-card transition-all hover:border-workspace-accent hover:shadow-lg"
    >
      <div className="flex gap-4 p-4">
        {/* Image or placeholder */}
        <div className="relative h-24 w-24 flex-shrink-0 overflow-hidden rounded-lg bg-muted">
          {imageUrl ? (
            <Image
              src={imageUrl}
              alt={result.title}
              fill
              className="object-cover"
              unoptimized
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <ImageIcon size={32} className="text-muted-foreground/50" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Header row */}
          <div className="mb-1 flex items-center gap-2">
            <span className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium', colorClass)}>
              <IconComponent size={12} />
              {source?.name || result.sourceId}
            </span>
            <span className="text-xs text-muted-foreground">
              #{rank}
            </span>
            {result.relevance !== undefined && (
              <span className="ml-auto text-xs font-medium text-workspace-accent">
                {Math.round(result.relevance * 100)}%
              </span>
            )}
          </div>

          {/* Title */}
          <h3 className="mb-1 truncate text-base font-semibold group-hover:text-workspace-accent">
            {result.title}
          </h3>

          {/* Snippet */}
          <p className="line-clamp-2 text-sm text-muted-foreground">
            {result.snippet}
          </p>

          {/* URL */}
          {result.url && (
            <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
              <ExternalLink size={12} />
              <span className="truncate">
                {(() => {
                  try {
                    return new URL(result.url).hostname;
                  } catch {
                    return result.url;
                  }
                })()}
              </span>
            </div>
          )}
        </div>
      </div>
    </a>
  );
}

export function WebSearchPanel({ query }: { query: string }) {
  const [showFilters, setShowFilters] = useState(false);
  const { sources, query: lastQuery, results, loading, error, toggleSource, search } = useSearchStore();

  useEffect(() => {
    if (query.trim() && query !== lastQuery) void search(query);
  }, [query, lastQuery, search]);

  const invalidate = useSearchScopesStore((s) => s.invalidate);
  // Only the engines /api/search/web implements; toggling one reruns the search.
  const engines = sources.filter((s) => WEB_ENGINE_IDS.includes(s.id));
  const enabledSources = engines.filter((s) => s.enabled);
  const groups: [string, SearchSource[]][] = [['Web engines', engines]];
  const sortedResults = [...results].sort((a, b) => (b.relevance || 0) - (a.relevance || 0));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {loading ? 'Searching…' : sortedResults.length > 0 && lastQuery
            ? <>Found <span className="font-medium text-foreground">{sortedResults.length}</span> results for &ldquo;{lastQuery}&rdquo;</>
            : enabledSources.length ? `Searching ${enabledSources.map((s) => s.name).join(' and ')}` : 'No web engine is switched on'}
        </p>
        <button
          type="button"
          onClick={() => setShowFilters(!showFilters)}
          className={cn(
            'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
            showFilters ? 'bg-workspace-accent text-white' : 'bg-secondary hover:bg-secondary/80'
          )}
        >
          <Filter size={14} />
          Engines ({enabledSources.length})
        </button>
      </div>

      {showFilters && (
        <div className="space-y-4 rounded-xl border bg-card p-4">
          {groups.filter(([, items]) => items.length > 0).map(([label, items]) => (
            <div key={label}>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</h4>
              <div className="flex flex-wrap gap-2">
                {items.map((source) => (
                  <SourceToggle key={source.id} source={source} onToggle={() => { toggleSource(source.id); invalidate(WEB_SCOPE); }} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-red-500">{error}</div>
      )}

      {sortedResults.length > 0 ? (
        <div className="space-y-3">
          {sortedResults.map((result, index) => (
            <ResultCard
              key={result.id}
              result={result}
              source={sources.find((s) => s.id === result.sourceId)}
              rank={index + 1}
            />
          ))}
        </div>
      ) : lastQuery && !loading ? (
        <div className="rounded-lg border bg-card p-6 text-center text-muted-foreground">
          No results found for &ldquo;{lastQuery}&rdquo;. Try different keywords or enable more sources.
        </div>
      ) : !query.trim() ? (
        <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          Type in the search box to search Wikipedia and DuckDuckGo.
        </div>
      ) : null}
    </div>
  );
}
