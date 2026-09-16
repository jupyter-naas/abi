'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import { X } from 'lucide-react';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { buildTermGraph, filterTermGraph } from '@/lib/ontology-term-graph';
import { buildProcessGraph, PROCESS_BUCKET_DEFS, processPresentationRoute } from '@/lib/ontology-process-graph';
import { termRoute } from '@/lib/ontology-navigation';
import { termKey } from '@/lib/ontology-context';
import { ontologySpacing, spaceOntologyNodes } from '@/lib/ontology-spacing';
import { usePublishOntologySystemTree } from '@/hooks/use-ontology-system-tree';
import { OntologyNodeInspector } from './ontology-node-inspector';
import './ontology-term-network.css';

const VisNetwork = dynamic(() => import('@/components/graph/vis-network').then(module => module.VisNetwork), { ssr: false });
const BFOBucketFilters = dynamic(() => import('@/components/graph/vis-network').then(module => module.BFOBucketFilters), { ssr: false });

export function OntologyTermNetwork({ term, terms, systemSidebar = false }: { term: DictionaryTerm; terms: DictionaryTerm[]; systemSidebar?: boolean }) {
  const router = useRouter(); const params = useSearchParams();
  const spacing = ontologySpacing(params?.toString() || '');
  const [hierarchy, setHierarchy] = useState(true);
  const [restrictions, setRestrictions] = useState(true);
  const [properties, setProperties] = useState(true);
  const [layout, setLayout] = useState<'network' | 'TD' | 'LR'>('network');
  const [activeBuckets, setActiveBuckets] = useState<Set<string>>(new Set());
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [focusRequestKey, setFocusRequestKey] = useState(0);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const graph = useMemo(() => buildTermGraph(term, terms), [term, terms]);
  const processGraph = useMemo(() => systemSidebar ? buildProcessGraph(term, terms) : null, [systemSidebar, term, terms]);
  const processView = Boolean(processGraph && params?.get('processView') !== 'ontology');
  const displayedGraph = processView ? processGraph! : graph;
  const relationGraph = useMemo(() => processView ? processGraph! : filterTermGraph(graph, { hierarchy, restrictions, properties }), [processView, processGraph, graph, hierarchy, restrictions, properties]);
  const visible = useMemo(() => processView ? processGraph! : filterTermGraph(graph, { hierarchy, restrictions, properties }, activeBuckets, hiddenNodeIds), [processView, processGraph, graph, hierarchy, restrictions, properties, activeBuckets, hiddenNodeIds]);
  const canvasNodes = useMemo(() => processView ? spaceOntologyNodes(visible.nodes, spacing.scale) : visible.nodes, [visible.nodes, processView, spacing.scale]);
  const nodesById = useMemo(() => new Map(displayedGraph.nodes.map(node => [node.id, node])), [displayedGraph.nodes]);
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
  function selectNode(id: string | null) {
    setSelectedNodeId(id); setSelectedEdgeId(null);
    if (id) setFocusRequestKey(value => value + 1);
  }

  function navigate(target: DictionaryTerm, network: boolean) {
    const next = termRoute(params?.toString() || '', target);
    if (network) next.set('view', 'network');
    router.push(`?${next}`, { scroll: false });
  }
  function changePresentation(presentation: 'process' | 'ontology', nodeId?: string) {
    const node = processGraph?.nodes.find(item => item.id === nodeId);
    setSelectedNodeId(presentation === 'ontology' && nodeId ? String(node?.properties.formal_term_id || graph.rootId) : null);
    setSelectedEdgeId(null);
    router.replace(`?${processPresentationRoute(params?.toString() || '', presentation)}`, { scroll: false });
  }
  function toggleBucket(bucket: string) {
    setActiveBuckets(previous => { const next = new Set(previous); if (next.has(bucket)) next.delete(bucket); else next.add(bucket); return next; });
  }
  function toggleNode(id: string) {
    setHiddenNodeIds(previous => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }

  usePublishOntologySystemTree(systemSidebar, {
    nodes: relationGraph.nodes, edges: relationGraph.edges, selectedNodeId: selectedNode?.id || null,
    onSelect: selectNode,
    bucketDefinitions: processView ? PROCESS_BUCKET_DEFS : undefined, bucketHeading: processView ? 'Process buckets' : undefined,
    onOpen: selectNode, canOpen: id => visible.nodes.some(node => node.id === id), openLabel: 'Inspect',
  });

  return <section className="ontology-term-network" aria-label={`Network for ${term.name}`}>
    <div className="ontology-term-toolbar">
      <h1><button type="button" className="ontology-term-title" title={`Inspect ${term.name}`} aria-expanded={selectedNode?.id === graph.rootId} onClick={() => selectNode(graph.rootId)}>{term.name}</button></h1>
      {processGraph && <div className="ontology-term-presentation" role="group" aria-label="Process presentation">
        <button type="button" aria-pressed={processView} onClick={() => changePresentation('process')}>Process</button>
        <button type="button" aria-pressed={!processView} onClick={() => changePresentation('ontology')}>Ontology</button>
      </div>}
      {!processView && <>
        <div className="ontology-term-controls" role="group" aria-label="Show relationships">
          <label title="Show the class hierarchy and ancestors">
            <input type="checkbox" checked={hierarchy} onChange={event => setHierarchy(event.target.checked)} />
            {term.type === 'entity' ? 'SubclassOf' : 'Hierarchy'}
          </label>
          <label title="Show restrictions declared on this term and its ancestors">
            <input type="checkbox" checked={restrictions} onChange={event => setRestrictions(event.target.checked)} />Restrictions
          </label>
          <label title="Show property relationships">
            <input type="checkbox" checked={properties} onChange={event => setProperties(event.target.checked)} />Properties
          </label>
        </div>
        <label className="ontology-term-layout">Layout
          <select value={layout} onChange={event => setLayout(event.target.value as 'network' | 'TD' | 'LR')}>
            <option value="network">Network</option>
            <option value="TD">Top to bottom</option>
            <option value="LR">Left to right</option>
          </select>
        </label>
      </>}
    </div>
    <div className="ontology-term-body" onKeyDown={event => { if (event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); selectNode(null); } }}>
    <div className="ontology-term-canvas" data-process-overview={processView || undefined} data-bucket-legend={!systemSidebar || undefined}>
      <div className="ontology-term-viewport">
        <VisNetwork key={`${processView ? 'process' : 'ontology'}:${layout}`} spacingKey={spacing.value} minimumAutoFitScale={1} nodes={canvasNodes} edges={visible.edges} selectedNodeId={selectedNode?.id || null}
          selectedEdgeIds={selectedEdge ? [selectedEdge.id] : []}
          onNodeSelect={selectNode}
          onEdgeSelect={id => { setSelectedEdgeId(id); if (id) setSelectedNodeId(null); }}
          onNodeDoubleClick={selectNode}
          orthogonalEdges={params?.get('connectors') !== 'curved'}
          nodeSpacing={processView ? undefined : spacing.gap} fixedLayout={processView} processOverview={processView}
          layoutDirection={processView || layout === 'network' ? undefined : layout}
          physicsEnabled={false} fillContainer preserveZoomOnSelection preserveZoomOnResize focusOnSelection focusRequestKey={focusRequestKey}
          viewStateKey={processView ? `ontology:process:${graph.rootId}` : `ontology:term:${graph.rootId}:${layout}:${hierarchy}:${restrictions}:${properties}`}
        />
      </div>
      {!systemSidebar && <BFOBucketFilters activeBuckets={activeBuckets} onToggle={toggleBucket} nodesPerBucket={nodesPerBucket} hiddenNodeIds={hiddenNodeIds} onNodeToggle={toggleNode} />}
    </div>
    {selectedNode && <OntologyNodeInspector node={selectedNode} nodes={visible.nodes} edges={visible.edges} terms={terms}
      context={systemSidebar ? term : undefined} onClose={() => selectNode(null)} onSelect={selectNode}
      onOpenFullPage={target => navigate(target, false)} onFocus={() => selectNode(selectedNode.id)}
      onExplore={processView ? () => changePresentation('ontology', selectedNode.id) : selected && selectedNode.id !== graph.rootId ? () => navigate(selected, true) : undefined}
      exploreLabel={processView ? 'View ontology' : 'Explore connections'} />}
    </div>
    <div className="ontology-term-status" aria-live="polite">
      {selectedEdge ? <span title={(selectedEdge.properties?.source_files as Array<{path: string}> || []).map(file => file.path).join('\n')}>
        {nodesById.get(selectedEdge.source)?.label} → {selectedEdge.label} → {nodesById.get(selectedEdge.target)?.label}
        {selectedEdge.properties?.declaration === 'domain / range' && ' · Domain / range declaration'}
      </span> : <span title={processView ? "Original ledger groupings. Ontology shows formal BFO types and relationships." : undefined}>{processView ? `Ledger overview · ${visible.nodes.length - 1} elements` : `${visible.nodes.length} terms · ${visible.edges.length} connections`}</span>}
      {selectedEdge && <button type="button" aria-label="Clear selection" onClick={() => { setSelectedNodeId(null); setSelectedEdgeId(null); }}><X size={12} /></button>}
      {!selectedNode && !selectedEdge && <span className="ontology-term-status-hint">Select a node to inspect</span>}
      {!processView && (activeBuckets.size > 0 || hiddenNodeIds.size > 0) && <button type="button" onClick={() => { setActiveBuckets(new Set()); setHiddenNodeIds(new Set()); }}>Reset filters</button>}
    </div>
  </section>;
}
