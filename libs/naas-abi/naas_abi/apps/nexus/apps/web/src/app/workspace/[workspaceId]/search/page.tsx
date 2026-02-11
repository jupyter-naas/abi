'use client';

import { useState, useCallback } from 'react';
import Image from 'next/image';
import {
  Search as SearchIcon,
  Filter,
  Clock,
  X,
  Globe,
  Shield,
  BookOpen,
  MessageSquare,
  FileCode,
  GitBranch,
  Network,
  Users,
  ExternalLink,
  Loader2,
  ImageIcon,
  type LucideIcon,
} from 'lucide-react';
import { Header } from '@/components/shell/header';
import { cn } from '@/lib/utils';
import { useSearchStore, type SearchSource, type SearchResult } from '@/stores/search';

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
      className="group block rounded-xl border bg-card transition-all hover:border-workspace-accent/50 hover:shadow-lg"
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

export default function SearchPage() {
  const [inputValue, setInputValue] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  
  const {
    sources,
    query,
    results,
    loading,
    error,
    recentSearches,
    toggleSource,
    search,
    clearResults,
    clearRecentSearches,
  } = useSearchStore();

  const enabledSources = sources.filter((s) => s.enabled);
  const publicSources = sources.filter((s) => s.category === 'public');
  const privateSources = sources.filter((s) => s.category === 'private');
  const customSources = sources.filter((s) => s.category === 'custom');

  const handleSearch = useCallback((searchQuery: string) => {
    if (searchQuery.trim()) {
      search(searchQuery);
    }
  }, [search]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(inputValue);
  };

  const handleClear = () => {
    setInputValue('');
    clearResults();
  };

  // Sort all results by relevance (already sorted from store, but ensure)
  const sortedResults = [...results].sort((a, b) => (b.relevance || 0) - (a.relevance || 0));

  return (
    <div className="flex h-full flex-col">
      <Header title="Search" subtitle="Semantic search across all your knowledge" />

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-4xl">
          {/* Search input */}
          <form onSubmit={handleSubmit} className="mb-4">
            <div className="flex items-center gap-3 rounded-xl border bg-card p-3 shadow-sm">
              {loading ? (
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              ) : (
                <SearchIcon size={20} className="text-muted-foreground" />
              )}
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Search across conversations, documents, web, and more..."
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              {inputValue && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <X size={16} />
                </button>
              )}
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                  showFilters ? 'bg-workspace-accent text-white' : 'bg-secondary hover:bg-secondary/80'
                )}
              >
                <Filter size={14} />
                Sources ({enabledSources.length})
              </button>
            </div>
          </form>

          {/* Source filters */}
          {showFilters && (
            <div className="mb-6 space-y-4 rounded-xl border bg-card p-4">
              {/* Public Sources */}
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Public Sources
                </h4>
                <div className="flex flex-wrap gap-2">
                  {publicSources.map((source) => (
                    <SourceToggle
                      key={source.id}
                      source={source}
                      onToggle={() => toggleSource(source.id)}
                    />
                  ))}
                </div>
              </div>

              {/* Private Sources */}
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Private Sources
                </h4>
                <div className="flex flex-wrap gap-2">
                  {privateSources.map((source) => (
                    <SourceToggle
                      key={source.id}
                      source={source}
                      onToggle={() => toggleSource(source.id)}
                    />
                  ))}
                </div>
              </div>

              {/* Custom Sources */}
              {customSources.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Custom Sources
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {customSources.map((source) => (
                      <SourceToggle
                        key={source.id}
                        source={source}
                        onToggle={() => toggleSource(source.id)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-red-500">
              {error}
            </div>
          )}

          {/* Results */}
          {sortedResults.length > 0 ? (
            <div className="space-y-4">
              {/* Results header */}
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Found <span className="font-medium text-foreground">{sortedResults.length}</span> results for &ldquo;{query}&rdquo;
                </p>
                <p className="text-xs text-muted-foreground">
                  Ranked by relevance
                </p>
              </div>

              {/* Single column results */}
              <div className="space-y-3">
                {sortedResults.map((result, index) => {
                  const source = sources.find((s) => s.id === result.sourceId);
                  return (
                    <ResultCard 
                      key={result.id} 
                      result={result} 
                      source={source} 
                      rank={index + 1}
                    />
                  );
                })}
              </div>
            </div>
          ) : query && !loading ? (
            <div className="rounded-lg border bg-card p-6 text-center">
              <p className="text-muted-foreground">
                No results found for "{query}". Try different keywords or enable more sources.
              </p>
            </div>
          ) : !query ? (
            /* Empty state */
            <div className="flex flex-col items-center py-16 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <SearchIcon size={32} className="text-muted-foreground" />
              </div>
              <h2 className="mb-2 text-lg font-semibold">Unified Search</h2>
              <p className="mb-6 max-w-md text-muted-foreground">
                Search across web (Google, Brave, DuckDuckGo), your conversations, files,
                knowledge graph, and custom sources. All in one place.
              </p>
              
              {/* Active sources indicator */}
              <div className="mb-6">
                <p className="mb-2 text-sm text-muted-foreground">
                  Searching {enabledSources.length} sources:
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {enabledSources.map((source) => {
                    const Icon = iconMap[source.icon] || Globe;
                    return (
                      <span
                        key={source.id}
                        className="flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs"
                      >
                        <Icon size={12} />
                        {source.name}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Recent Searches */}
              {recentSearches.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-muted-foreground">Recent Searches</h3>
                    <button
                      onClick={clearRecentSearches}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      Clear
                    </button>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {recentSearches.slice(0, 5).map((term) => (
                      <button
                        key={term}
                        onClick={() => {
                          setInputValue(term);
                          handleSearch(term);
                        }}
                        className="flex items-center gap-2 rounded-lg bg-secondary px-3 py-1.5 text-sm transition-colors hover:bg-secondary/80"
                      >
                        <Clock size={12} />
                        {term}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
