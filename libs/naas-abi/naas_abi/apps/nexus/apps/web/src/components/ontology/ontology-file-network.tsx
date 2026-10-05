'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import type { DashboardRestriction } from '@/lib/ontology-dashboard';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { buildFileNetwork, type ProcessSlice } from '@/lib/ontology-file-network';

const VisNetwork = dynamic(() => import('@/components/graph/vis-network').then(module => module.VisNetwork), { ssr: false });

type Slices = { path: string; items: ProcessSlice[]; loading: boolean; error?: string };

/**
 * One ontology file as a network in the BFO 7 buckets layout: its classes and
 * the restrictions it states. A consolidated module ontology can be narrowed
 * to the process slices it carries.
 */
export function OntologyFileNetwork({ workspaceId, path, fileTerms, restrictions, terms, selectedNodeId, onSelect }: {
  workspaceId: string; path: string; fileTerms: DictionaryTerm[]; restrictions: DashboardRestriction[]; terms: DictionaryTerm[];
  selectedNodeId: string | null; onSelect: (nodeId: string | null) => void;
}) {
  const [slices, setSlices] = useState<Slices | null>(null);
  const [selected, setSelected] = useState<{ path: string; ids: Set<string> }>({ path, ids: new Set() });
  const [zoneBuckets, setZoneBuckets] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setSlices({ path, items: [], loading: true });
    void (async () => {
      try {
        const response = await authFetch(`${getApiUrl()}/api/ontology/process-slices?${new URLSearchParams({ workspace_id: workspaceId, path })}`);
        if (!response.ok) throw new Error('Could not load the process files.');
        const data: { items?: ProcessSlice[] } = await response.json();
        if (!cancelled) setSlices({ path, items: Array.isArray(data.items) ? data.items : [], loading: false });
      } catch (error) {
        if (!cancelled) setSlices({ path, items: [], loading: false, error: error instanceof Error ? error.message : 'Could not load the process files.' });
      }
    })();
    return () => { cancelled = true; };
  }, [workspaceId, path]);

  const items = useMemo(() => slices?.path === path ? slices.items : [], [slices, path]);
  const chosen = useMemo(() => selected.path === path ? selected.ids : new Set<string>(), [selected, path]);
  const network = useMemo(() => buildFileNetwork(fileTerms, restrictions, terms, items, chosen), [fileTerms, restrictions, terms, items, chosen]);
  const toggle = (id: string) => setSelected(current => {
    const ids = new Set(current.path === path ? current.ids : []);
    if (ids.has(id)) ids.delete(id); else ids.add(id);
    return { path, ids };
  });

  return <section className="ontology-dashboard-network" aria-label="Ontology network">
    <div className="ontology-dashboard-network-toolbar">
      {items.length > 0 && <div className="ontology-dashboard-network-processes" role="group" aria-label="Filter by process file">
        <span>Processes</span>
        <button type="button" aria-pressed={!chosen.size} onClick={() => setSelected({ path, ids: new Set() })}>All</button>
        {items.map(item => <button type="button" key={item.id} aria-pressed={chosen.has(item.id)} title={item.path} onClick={() => toggle(item.id)}>
          {item.name.replace(/\s+Process Ontology$/i, '').replace(/\s+Ontology$/i, '')}
        </button>)}
      </div>}
      {slices?.loading && <span role="status">Loading process files…</span>}
      {slices?.error && <span role="alert">{slices.error}</span>}
      <label title="Show a zone and its title for each BFO bucket"><input type="checkbox" checked={zoneBuckets} onChange={event => setZoneBuckets(event.target.checked)} />Zone 7 Buckets</label>
      <span className="ontology-dashboard-network-count">{network.nodes.length} classes · {network.edges.length} restrictions</span>
    </div>
    <div className="ontology-dashboard-network-canvas">
      {network.nodes.length ? <VisNetwork key={`${path}:${[...chosen].sort().join('|')}`} nodes={network.nodes} edges={network.edges}
        selectedNodeId={selectedNodeId} selectedEdgeIds={[]} onNodeSelect={onSelect} onEdgeSelect={() => undefined} onNodeDoubleClick={onSelect}
        orthogonalEdges bfoZones bfoZonesVisible={{ topLevel: false, buckets: zoneBuckets }} minimumAutoFitScale={0.35}
        physicsEnabled={false} fillContainer preserveZoomOnSelection preserveZoomOnResize
        viewStateKey={`ontology:file:${path}:${[...chosen].sort().join('|')}`} />
        : <p className="ontology-dashboard-empty">No classes or restrictions to draw.</p>}
    </div>
  </section>;
}
