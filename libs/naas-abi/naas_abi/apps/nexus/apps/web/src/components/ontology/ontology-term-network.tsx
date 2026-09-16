'use client';

import { useCallback, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, ArrowRight, GitBranch, X } from 'lucide-react';
import { buildHoverTitle } from '@/components/graph/vis-network';
import type { GraphNode } from '@/stores/knowledge-graph';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { buildTermGraph, filterTermGraph } from '@/lib/ontology-term-graph';
import { termRoute } from '@/lib/ontology-navigation';
import { termKey } from '@/lib/ontology-context';
import { usePublishOntologySystemTree } from '@/hooks/use-ontology-system-tree';
import './ontology-term-network.css';

const VisNetwork = dynamic(() => import('@/components/graph/vis-network').then(module => module.VisNetwork), { ssr: false });
const BFOBucketFilters = dynamic(() => import('@/components/graph/vis-network').then(module => module.BFOBucketFilters), { ssr: false });

export function OntologyTermNetwork({ term, terms, systemSidebar = false }: { term: DictionaryTerm; terms: DictionaryTerm[]; systemSidebar?: boolean }) {
  const router = useRouter(); const params = useSearchParams();
  const [hierarchy, setHierarchy] = useState(true);
  const [restrictions, setRestrictions] = useState(true);
  const [properties, setProperties] = useState(true);
  const [layout, setLayout] = useState<'network' | 'TD' | 'LR'>('network');
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const graph = useMemo(() => buildTermGraph(term, terms), [term, terms]);
  const relationGraph = useMemo(() => filterTermGraph(graph, { hierarchy, restrictions, properties }), [graph, hierarchy, restrictions, properties]);
  const visible = useMemo(() => filterTermGraph(graph, { hierarchy, restrictions, properties }, activeBuckets, hiddenNodeIds), [graph, hierarchy, restrictions, properties, activeBuckets, hiddenNodeIds]);
  const nodesById = useMemo(() => new Map(graph.nodes.map(node => [node.id, node])), [graph.nodes]);
  const nodesPerBucket = useMemo(() => {
    const buckets = new Map<string, { id: string; label: string }[]>();
    for (const node of relationGraph.nodes) {
      // The term being explored stays visible while its neighbours are filtered.
      if (node.id === graph.rootId) continue;
      const entries = buckets.get(node.type) || [];
      entries.push({ id: node.id, label: node.label }); buckets.set(node.type, entries);
    }
    for (const entries of buckets.values()) entries.sort((a, b) => a.label.localeCompare(b.label));
    return buckets;
  }, [relationGraph.nodes, graph.rootId]);
  const selected = terms.find(item => termKey(item) === selectedNodeId);
  const selectedNode = visible.nodes.find(node => node.id === selectedNodeId);
  const selectedEdge = visible.edges.find(edge => edge.id === selectedEdgeId);
  const getNodeTitle = useCallback((node: GraphNode) => buildHoverTitle([
    ['Term', node.label], ['Type', String(node.properties.kind)], ['URI', String(node.properties.iri)],
    ['Definition', String(node.properties.definition || 'No definition in the workspace files.')],
  ]), []);

  function navigate(target: DictionaryTerm, network: boolean) {
    const next = termRoute(params?.toString() || '', target);
    if (network) next.set('view', 'network');
    router.push(`?${next}`, { scroll: false });
  }
  function toggleBucket(bucket: string) {
    setActiveBuckets(previous => { const next = new Set(previous); if (next.has(bucket)) next.delete(bucket); else next.add(bucket); return next; });
  }
  function toggleNode(id: string) {
    setHiddenNodeIds(previous => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }

  usePublishOntologySystemTree(systemSidebar, {
    nodes: relationGraph.nodes, edges: relationGraph.edges, selectedNodeId: selectedNode?.id || null,
    onSelect: id => { setSelectedNodeId(id); setSelectedEdgeId(null); },
    onOpen: id => { const target = terms.find(item => termKey(item) === id); if (target) navigate(target, false); },
    canOpen: id => terms.some(item => termKey(item) === id), openLabel: 'Open details',
  });

  return <section className="ontology-term-network" aria-label={`Network for ${term.name}`}>
    <div className="ontology-term-toolbar">
      <h1 title={term.name}>{term.name}</h1>
      <div className="ontology-term-controls" aria-label="Network relationships">
        <button type="button" aria-pressed={hierarchy} onClick={() => setHierarchy(value => !value)}><GitBranch size={12} />{term.type === 'entity' ? 'SubclassOf' : 'Hierarchy'}</button>
        <button type="button" aria-pressed={restrictions} onClick={() => setRestrictions(value => !value)}><AlertCircle size={12} />Restrictions</button>
        <button type="button" aria-pressed={properties} onClick={() => setProperties(value => !value)}><ArrowRight size={12} />Properties</button>
      </div>
      <div className="ontology-term-layout" aria-label="Network layout">
        {(['network', 'TD', 'LR'] as const).map(value => <button key={value} type="button" aria-pressed={layout === value} title={{ network: 'Connected network', TD: 'Top-down hierarchy', LR: 'Left-to-right hierarchy' }[value]} onClick={() => setLayout(value)}>{value === 'network' ? 'Network' : value}</button>)}
      </div>
      <button className="ontology-term-details" type="button" onClick={() => navigate(term, false)}>Open details</button>
    </div>
    <div className="ontology-term-canvas">
      <div className="ontology-term-viewport">
        <VisNetwork nodes={visible.nodes} edges={visible.edges} selectedNodeId={selectedNode?.id || null}
          selectedEdgeIds={selectedEdge ? [selectedEdge.id] : []}
          onNodeSelect={id => { setSelectedNodeId(id); setSelectedEdgeId(null); }}
          onEdgeSelect={id => { setSelectedEdgeId(id); if (id) setSelectedNodeId(null); }}
          layoutDirection={layout === 'network' ? undefined : layout}
          physicsEnabled={false} fillContainer getNodeTitle={getNodeTitle}
          viewStateKey={`ontology:term:${graph.rootId}:${layout}:${hierarchy}:${restrictions}:${properties}`}
        />
      </div>
      {!systemSidebar && <BFOBucketFilters activeBuckets={activeBuckets} onToggle={toggleBucket} nodesPerBucket={nodesPerBucket} hiddenNodeIds={hiddenNodeIds} onNodeToggle={toggleNode} />}
    </div>
    <div className="ontology-term-status" aria-live="polite">
      {selectedNode ? <>
        <span title={String(selectedNode.properties.iri)}>{selectedNode.label}</span>
        {selected && <>{selectedNode.id !== graph.rootId && <button type="button" onClick={() => navigate(selected, true)}>Focus here</button>}<button type="button" onClick={() => navigate(selected, false)}>Open details</button></>}
      </> : selectedEdge ? <span title={(selectedEdge.properties?.source_files as Array<{path: string}> || []).map(file => file.path).join('\n')}>
        {nodesById.get(selectedEdge.source)?.label} → {selectedEdge.label} → {nodesById.get(selectedEdge.target)?.label}
        {selectedEdge.properties?.declaration === 'domain / range' && ' · Domain / range declaration'}
      </span> : <span>{visible.nodes.length} terms · {visible.edges.length} connections</span>}
      {(selectedNode || selectedEdge) && <button type="button" aria-label="Clear selection" onClick={() => { setSelectedNodeId(null); setSelectedEdgeId(null); }}><X size={12} /></button>}
      {(activeBuckets.size > 0 || hiddenNodeIds.size > 0) && <button type="button" onClick={() => { setActiveBuckets(new Set()); setHiddenNodeIds(new Set()); }}>Reset filters</button>}
    </div>
  </section>;
}
