'use client';

import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SearchTopic, TopicResultItem } from '@/lib/search-topics';
import { SparqlDisclosure } from './sparql-disclosure';
import { TopicAvatar } from './topic-avatar';

/** The results list: one renderer for every topic, filled from the results-role slots. */
export function TopicResults({
  topic, query, items, loading, error, hasMore, sparql, selected, hrefFor, onMore,
}: {
  topic: SearchTopic;
  query: string;
  items: TopicResultItem[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  sparql: string;
  selected: string | null;
  hrefFor: (uri: string) => string;
  onMore: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-col gap-2">
      <div className="flex items-center justify-between gap-2 px-1 text-xs text-muted-foreground">
        <span aria-live="polite">
          {loading && !items.length ? 'Searching…'
            : `${items.length}${hasMore ? '+' : ''} ${(items.length === 1 ? topic.label : topic.plural_label).toLowerCase()}${query ? ` matching “${query}”` : ''}`}
        </span>
        <SparqlDisclosure sparql={sparql} className="text-right" />
      </div>

      {error && <div role="alert" className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No {topic.plural_label.toLowerCase()} {query ? <>match &ldquo;{query}&rdquo;</> : 'in the graphs this workspace can read'}.
        </div>
      )}

      <ul className="space-y-1.5">
        {items.map(item => (
          <li key={item.uri}>
            <Link
              href={hrefFor(item.uri)}
              scroll={false}
              aria-current={selected === item.uri ? 'true' : undefined}
              className={cn(
                'flex gap-3 rounded-lg border bg-card p-3 transition-colors hover:border-workspace-accent',
                selected === item.uri && 'border-workspace-accent bg-workspace-accent-10',
              )}
            >
              <TopicAvatar label={item.title} image={item.image} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{item.title}</div>
                {item.subtitle && <div className="truncate text-xs text-muted-foreground">{item.subtitle}</div>}
                {item.snippet && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.snippet}</p>}
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {hasMore && (
        <button
          type="button"
          onClick={onMore}
          disabled={loading}
          className="mx-auto flex items-center gap-2 rounded-lg bg-secondary px-3 py-1.5 text-xs font-medium hover:bg-secondary/80 disabled:opacity-60"
        >
          {loading && <Loader2 size={12} className="animate-spin" />} Show more
        </button>
      )}
    </div>
  );
}
