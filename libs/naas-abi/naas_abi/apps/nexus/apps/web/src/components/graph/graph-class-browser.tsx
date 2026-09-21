'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Search } from 'lucide-react';
import { useGraphClassCatalog } from '@/stores/graph-class-catalog';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { useOntologyIconsStore } from '@/stores/ontology-icons';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import './instance-browser.css';

export function GraphClassBrowser({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const query = useSearchParams();
  const catalog = useGraphClassCatalog(state => state.snapshot);
  const selectedGraphId = useKnowledgeGraphStore(state => state.selectedGraphId);
  const loadIcons = useOntologyIconsStore(state => state.load);
  const [search, setSearch] = useState('');
  const requestedGraph = query.get('graph');
  const selectedClass = query.get('class');
  const scopeMatches = catalog?.workspaceId === workspaceId && (requestedGraph ? catalog.graphUri === requestedGraph : !selectedGraphId || catalog.graphId === selectedGraphId);
  const classes = useMemo(() => scopeMatches ? [...catalog.classes]
    .filter(item => item.class_uri && (item.class_label || item.class_uri).toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => (a.class_label || a.class_uri).localeCompare(b.class_label || b.class_uri)) : [], [catalog, scopeMatches, search]);

  useEffect(() => { void loadIcons(workspaceId); }, [workspaceId, loadIcons]);
  useEffect(() => { setSearch(''); }, [workspaceId, catalog?.graphUri]);

  const selectClass = (uri: string) => {
    if (!catalog || !scopeMatches) return;
    const next = new URLSearchParams(query.toString());
    next.set('graph', catalog.graphUri);
    next.set('class', uri);
    router.replace(`/workspace/${workspaceId}/graph/network?${next}`, { scroll: false });
  };

  if (!scopeMatches) return null;
  return <section className="graph-class-browser" aria-label="Classes in selected graph">
    <header><span>Classes</span><span>{catalog.classes.length.toLocaleString()}</span></header>
    <label className="graph-browser-search"><Search size={14} /><input aria-label="Search classes" placeholder="Search classes…" value={search} onChange={event => setSearch(event.target.value)} /></label>
    <p className="graph-browser-scope" title={catalog.graphUri}>{catalog.graphLabel}</p>
    {catalog.loading ? <p className="graph-browser-message" role="status">Loading classes…</p> : catalog.error ? <p className="graph-browser-message" role="alert">{catalog.error}</p> : <ul className="graph-class-list">
      {classes.map((item, index) => <li key={item.class_uri}><button type="button" aria-current={selectedClass === item.class_uri ? 'true' : undefined} onClick={() => selectClass(item.class_uri)} onKeyDown={event => {
        const target = event.key === 'ArrowDown' ? index + 1 : event.key === 'ArrowUp' ? index - 1 : event.key === 'Home' ? 0 : event.key === 'End' ? classes.length - 1 : -1;
        if (target < 0 || target >= classes.length) return;
        event.preventDefault();
        const buttons = event.currentTarget.closest('ul')?.querySelectorAll('button');
        buttons?.[target]?.focus();
        selectClass(classes[target].class_uri);
      }} title={item.class_label || item.class_uri}>
        <OntologyTopicIcon subject={{ id: item.class_uri, name: item.class_label, type: 'entity' }} className="graph-browser-small-icon" />
        <span>{item.class_label || item.class_uri}</span><small>{item.count.toLocaleString()}</small>
      </button></li>)}
    </ul>}
    {!catalog.loading && !catalog.error && classes.length === 0 && <p className="graph-browser-message">{search ? 'No matching classes.' : 'No instance classes yet.'}</p>}
  </section>;
}
