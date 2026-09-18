'use client';
import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { GraphHeader } from './graph-header';
import { IndividualDetailPanel, type InstanceDetail } from './instance-detail-editor';
import { useGraphRequest } from '@/hooks/use-graph-request';
import { authFetch, useAuthStore } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import type { ExplorerGraph } from '@/lib/graph-explorer';
import { explorerQuery } from '@/lib/graph-explorer';
import './graph-object.css';

export function GraphObjectPage({workspaceId, graphUri, instanceUri}: {workspaceId: string; graphUri: string; instanceUri: string}) {
  const userId = useAuthStore(s => s.user?.id);
  const router = useRouter();
  const query = useSearchParams().toString();
  const key = JSON.stringify([workspaceId, graphUri, userId]);
  const [catalog, setCatalog] = useState<{key: string; graphs: ExplorerGraph[]; error: string | null} | null>(null);
  const [attempt, setAttempt] = useState(0);
  const detail = useGraphRequest<InstanceDetail>('discovery/instance-detail', {
    workspace_id: workspaceId, graph_uri: graphUri, instance_uri: instanceUri,
  }, Boolean(graphUri && instanceUri));
  useEffect(() => {
    const controller = new AbortController();
    void authFetch(`${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`, {signal: controller.signal})
      .then(async response => {
        if (!response.ok) throw new Error('Graph permissions could not be loaded.');
        const packs = await response.json() as Array<{graphs: ExplorerGraph[]}>;
        if (!controller.signal.aborted) setCatalog({key, graphs: packs.flatMap(pack => pack.graphs), error: null});
      }).catch((error: unknown) => {
        if (!controller.signal.aborted) setCatalog({key, graphs: [], error: error instanceof Error ? error.message : 'Graph permissions could not be loaded.'});
      });
    return () => controller.abort();
  }, [workspaceId, key, attempt]);
  const current = catalog?.key === key ? catalog : null;
  const graph = current?.graphs.find(g => g.uri === graphUri);
  const isSchema = graphUri === 'http://ontology.naas.ai/graph/schema';
  const canWrite = graph?.can_write === true && !isSchema;
  const listQuery = explorerQuery(query, {selected: null, view: 'instances'});
  const back = `/workspace/${workspaceId}/graph/explorer?${listQuery}`;
  const retryDetail = detail.retry;
  const refresh = useCallback(() => { retryDetail(); setAttempt(value => value + 1); }, [retryDetail]);
  useEffect(() => {
    window.addEventListener('graph-cache-refresh', refresh);
    return () => window.removeEventListener('graph-cache-refresh', refresh);
  }, [refresh]);
  const changed = () => window.dispatchEvent(new Event('graph-cache-refresh'));
  return <div className="graph-object-page">
    <GraphHeader />
    <div className="graph-object-toolbar">
      <Link href={back}><ArrowLeft size={14} />Instances</Link>
      <span>{graph?.label || 'Instance'}{current && !current.error && graph ? ` · ${canWrite ? 'Editable' : 'Read-only'}` : ''}</span>
      <button type="button" onClick={refresh} aria-label="Refresh instance"><RefreshCw size={14} /></button>
    </div>
    <main className="graph-object-content">
      {!graphUri ? <p className="graph-object-error" role="alert">Select a graph to open this instance.</p> : detail.error ? <p className="graph-object-error" role="alert">{detail.error} <button onClick={detail.retry}>Retry</button></p> : detail.loading || !detail.data ? <p className="graph-object-status" role="status">Loading instance…</p> : <>
        {isSchema && <p className="graph-object-notice">This instance comes from the Schema graph. Its properties are managed in the source ontology and are read-only here.</p>}
        {!isSchema && current && !canWrite && !current.error && <p className="graph-object-notice">This graph is read-only in this workspace.</p>}
        {!current && <p className="graph-object-status" role="status">Checking edit access…</p>}
        {current?.error && <p className="graph-object-error" role="alert">{current.error} <button onClick={refresh}>Retry</button></p>}
        <IndividualDetailPanel key={`${key}:${instanceUri}`} workspaceId={workspaceId} graphUri={graphUri}
          readOnly={!canWrite} instance={{...detail.data, properties: {}}} detail={detail.data} loading={false}
          onPropertyDeleted={changed} onIndividualDeleted={() => {changed(); router.push(back);}} />
      </>}
    </main>
  </div>;
}
