'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { BookOpen, Contact, List } from 'lucide-react';
import { cn } from '@/lib/utils';
import { searchHref, type SearchRoute, type SearchTopic, type TopicDetail, type TopicResultItem } from '@/lib/search-topics';
import { topicsApi } from '@/lib/search-topics-api';
import { TopicDetailView } from './topic-detail';
import { TopicIcon } from './topic-icon';
import { TopicOntology } from './topic-ontology';
import { TopicResults } from './topic-results';

const PAGE_SIZE = 30;

/**
 * A SPARQL topic on its own, in three tabs: the results list (with paging), the
 * topic's ontology, and the detail of one individual under the topic's detail
 * label ("Profile" for a person, "Card" for an organization). Opening a result
 * switches to that tab; until one is opened it is empty.
 */
export function TopicScopeView({ workspaceId, topic, route, canEdit, onTab }: {
  workspaceId: string;
  topic: SearchTopic;
  route: SearchRoute;
  canEdit: boolean;
  onTab: (tab: SearchRoute['tab']) => void;
}) {
  const [results, setResults] = useState<{ items: TopicResultItem[]; hasMore: boolean; sparql: string; error: string | null; loading: boolean }>(
    { items: [], hasMore: false, sparql: '', error: null, loading: false },
  );
  const resultsSeq = useRef(0);
  const fetchResults = useCallback(async (offset: number) => {
    const seq = ++resultsSeq.current;
    setResults(r => ({ ...r, loading: true, error: null, ...(offset === 0 ? { items: [] } : {}) }));
    try {
      const page = await topicsApi.results(workspaceId, topic.id, route.q, offset, PAGE_SIZE);
      if (seq !== resultsSeq.current) return;
      setResults(r => ({
        items: offset === 0 ? page.items : [...r.items, ...page.items],
        hasMore: page.has_more,
        sparql: page.sparql,
        error: null,
        loading: false,
      }));
    } catch (error) {
      if (seq !== resultsSeq.current) return;
      setResults(r => ({ ...r, loading: false, error: error instanceof Error ? error.message : 'Search failed' }));
    }
  }, [workspaceId, topic, route.q]);
  useEffect(() => { void fetchResults(0); }, [fetchResults]);

  const [detail, setDetail] = useState<{ data: TopicDetail | null; loading: boolean; error: string | null }>({ data: null, loading: false, error: null });
  useEffect(() => {
    if (!route.item) { setDetail({ data: null, loading: false, error: null }); return; }
    let cancelled = false;
    setDetail(d => ({ data: d.data?.uri === route.item ? d.data : null, loading: true, error: null }));
    topicsApi.detail(workspaceId, topic.id, route.item)
      .then(data => { if (!cancelled) setDetail({ data, loading: false, error: null }); })
      .catch(error => { if (!cancelled) setDetail({ data: null, loading: false, error: error instanceof Error ? error.message : 'Could not load details' }); });
    return () => { cancelled = true; };
  }, [workspaceId, topic, route.item]);

  const hrefFor = (uri: string) => searchHref(workspaceId, { ...route, scope: topic.id, item: uri, tab: 'details' });
  const linkFor = (topicId: string, uri: string) => searchHref(workspaceId, { scope: topicId, item: uri, tab: 'details' });
  // Back to the list keeps the opened individual, so its tab still holds it.
  const backHref = searchHref(workspaceId, { ...route, scope: topic.id, tab: 'results' });
  const detailLabel = topic.detail_label || 'Details';

  return (
    <>
      <div className="flex items-center gap-1 border-b text-sm" role="tablist">
        <SubTab active={route.tab === 'results'} onClick={() => onTab('results')}><List size={14} /> Results</SubTab>
        <SubTab active={route.tab === 'ontology'} onClick={() => onTab('ontology')}><BookOpen size={14} /> Ontology</SubTab>
        <SubTab active={route.tab === 'details'} onClick={() => onTab('details')}><Contact size={14} /> {detailLabel}</SubTab>
      </div>

      {route.tab === 'ontology' ? (
        <TopicOntology workspaceId={workspaceId} topic={topic} />
      ) : route.tab === 'details' ? (
        route.item ? (
          <TopicDetailView detail={detail.data} loading={detail.loading} error={detail.error} backHref={backHref} linkFor={linkFor} />
        ) : (
          <div className="flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            <TopicIcon name={topic.icon} size={28} className="mb-2 opacity-50" />
            Open a {topic.label.toLowerCase()} from the results to see its {detailLabel.toLowerCase()} here.
          </div>
        )
      ) : (
        <TopicResults
          topic={topic}
          query={route.q}
          items={results.items}
          loading={results.loading}
          error={results.error}
          hasMore={results.hasMore}
          sparql={results.sparql}
          selected={route.item}
          hrefFor={hrefFor}
          onMore={() => void fetchResults(results.items.length)}
        />
      )}
    </>
  );
}

function SubTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        '-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2',
        active ? 'border-workspace-accent text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
      )}
    >
      {children}
    </button>
  );
}
