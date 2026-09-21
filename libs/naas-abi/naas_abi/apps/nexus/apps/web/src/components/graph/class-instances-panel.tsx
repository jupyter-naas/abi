'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ArrowUpRight, Search, X } from 'lucide-react';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { useGraphRequest } from '@/hooks/use-graph-request';
import { classDefinitionHref, individualHref, instancePage, instancePageRequest, INSTANCE_PAGE_SIZE } from '@/lib/graph-instance-browser';
import { InstanceInspector, type DiscoveryInstance } from './instance-inspector';
import './instance-browser.css';

export function ClassInstancesPanel({ workspaceId, graphUri, graphLabel, classUri, classLabel, count, onClose }: {
  workspaceId: string; graphUri: string; graphLabel: string; classUri: string; classLabel: string; count: number; onClose: () => void;
}) {
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState('');
  const [instance, setInstance] = useState<DiscoveryInstance | null>(null);
  const request = useGraphRequest<DiscoveryInstance[]>('discovery/instances', instancePageRequest(workspaceId, graphUri, classUri, page, submittedSearch));
  const { rows, hasMore } = instancePage(request.data ?? []);

  return <aside className="graph-instance-panel" aria-label={`${classLabel} instances`}>
    {instance ? <>
      <button className="graph-browser-back" type="button" onClick={() => setInstance(null)}><ArrowLeft size={14} />Back to {classLabel}</button>
      <InstanceInspector key={instance.uri} instance={instance} graphUri={graphUri} graphLabel={graphLabel} workspaceId={workspaceId} onClose={onClose} onSelectInstance={setInstance} />
    </> : <>
      <header className="graph-browser-heading">
        <div><OntologyTopicIcon subject={{ id: classUri, name: classLabel, type: 'entity' }} /><h2>{classLabel}</h2><p>{count.toLocaleString()} instances · {graphLabel}</p></div>
        <button className="graph-browser-icon-button" type="button" aria-label="Close instances" onClick={onClose}><X size={16} /></button>
      </header>
      <div className="graph-browser-actions"><Link href={classDefinitionHref(workspaceId, classUri)}>Class definition <ArrowUpRight size={13} /></Link><Link href={individualHref(workspaceId, graphUri, classUri)}>Open table <ArrowUpRight size={13} /></Link></div>
      <form className="graph-browser-search graph-instance-search" onSubmit={event => { event.preventDefault(); setSubmittedSearch(search.trim()); setPage(0); }}>
        <Search size={14} /><input aria-label="Search instance labels" placeholder="Search labels, press Enter…" value={search} onChange={event => { setSearch(event.target.value); if (!event.target.value) { setSubmittedSearch(''); setPage(0); } }} />
      </form>
      <div className="graph-instance-results" aria-busy={request.loading}>
        {request.loading ? <p className="graph-browser-message" role="status">Loading instances…</p> : request.error ? <p className="graph-browser-message" role="alert">{request.error} <button type="button" onClick={request.retry}>Retry</button></p> : rows.length === 0 ? <p className="graph-browser-message">{submittedSearch ? 'No instances match this label.' : 'No instances on this page.'}</p> : <ul className="graph-instance-list">{rows.map(row => <li key={row.uri}><button type="button" onClick={() => setInstance(row)}>
          <OntologyTopicIcon subject={{ id: classUri, name: classLabel, type: 'entity' }} className="graph-browser-small-icon" /><span><strong>{row.label || row.uri}</strong><small title={row.uri}>{row.uri}</small></span>
        </button></li>)}</ul>}
      </div>
      <footer className="graph-browser-pagination"><button type="button" disabled={page === 0 || request.loading} onClick={() => setPage(value => value - 1)}>Previous</button><span aria-live="polite">{request.loading ? 'Loading…' : request.error ? 'Unavailable' : rows.length ? `${page * INSTANCE_PAGE_SIZE + 1}–${page * INSTANCE_PAGE_SIZE + rows.length}` : '0 results'}</span><button type="button" disabled={!hasMore || request.loading || !!request.error} onClick={() => setPage(value => value + 1)}>Next</button></footer>
    </>}
  </aside>;
}
