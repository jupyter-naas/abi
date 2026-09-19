'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { buildOntologySystems, buildSystemGraph, buildSystemsGraph, systemProcessLabel } from '@/lib/ontology-system-graph';
import { dictionaryFiles, filterTermsByFiles } from '@/lib/ontology-file-filter';
import { systemRoute, termRoute } from '@/lib/ontology-navigation';
import { filterSystems, selectedSystems, systemFilterRoute } from '@/lib/ontology-system-filter';
import { termKey } from '@/lib/ontology-context';
import { ontologySpacing, spaceOntologyNodes } from '@/lib/ontology-spacing';
import { OntologyTermNetwork } from './ontology-term-network';
import { usePublishOntologySystemTree } from '@/hooks/use-ontology-system-tree';
import { OntologyNodeInspector } from './ontology-node-inspector';
import './ontology-system-view.css';

const VisNetwork = dynamic(() => import('@/components/graph/vis-network').then(module => module.VisNetwork), { ssr: false });

export function OntologySystemView({ terms, loading, error, partial }: { terms: DictionaryTerm[]; loading: boolean; error: string | null; partial: boolean }) {
  const router = useRouter(); const params = useSearchParams();
  const query = params?.toString() || '';
  const spacing = ontologySpacing(query);
  // Presentation changes must not rebuild the layout or reset a manually chosen zoom.
  const filesQuery = new URLSearchParams(dictionaryFiles(query).map(path => ['dictionaryFile', path])).toString();
  const systemsQuery = new URLSearchParams(selectedSystems(query).map(id => ['systemFilter', id])).toString();
  const models = useMemo(() => buildOntologySystems(terms, filterTermsByFiles(terms, dictionaryFiles(filesQuery))), [terms, filesQuery]);
  const visibleSystems = useMemo(() => filterSystems(models, systemsQuery), [models, systemsQuery]);
  const requestedSystem = params?.get('system');
  const system = visibleSystems.find(model => model.term.id === requestedSystem) || (!requestedSystem && visibleSystems.length === 1 ? visibleSystems[0] : undefined);
  const subsystemId = params?.get('subsystem') || '';
  const processId = params?.get('process') || '';
  const subsystem = system?.subsystems.find(group => group.term.id === subsystemId);
  const processes = subsystem?.processes || system?.processes || [];
  const process = processes.find(term => term.id === processId);
  const graph = useMemo(() => system ? buildSystemGraph(system, subsystemId) : buildSystemsGraph(visibleSystems), [system, subsystemId, visibleSystems]);
  const canvasNodes = useMemo(() => spaceOntologyNodes(graph.nodes, spacing.scale), [graph.nodes, spacing.scale]);
  const graphKey = `${visibleSystems.map(model => model.term.id).join('|')}:${system?.term.id || ''}:${subsystemId}`;
  const processCount = system ? processes.length : new Set(visibleSystems.flatMap(model => model.processes.map(term => term.id))).size;
  const [selected, setSelected] = useState<string | null>(null);
  const [focusRequestKey, setFocusRequestKey] = useState(0);
  function selectNode(id: string | null) {
    setSelected(id);
    if (id) setFocusRequestKey(value => value + 1);
  }
  const selectedNode = graph?.nodes.find(node => node.id === selected);
  const selectedTerm = terms.find(term => termKey(term) === selectedNode?.id);
  const navigate = (systemId?: string, groupId?: string, termId?: string) => {
    setSelected(null);
    router.push(`?${systemRoute(query, systemId, groupId, termId)}`, { scroll: false });
  };
  function drill(id: string) {
    const owner = system || visibleSystems.find(model => termKey(model.term) === id || model.subsystems.some(group => termKey(group.term) === id) || model.processes.some(term => termKey(term) === id));
    if (!owner) return;
    if (id === termKey(owner.term)) { navigate(owner.term.id); return; }
    const group = owner.subsystems.find(item => termKey(item.term) === id);
    if (group) { navigate(owner.term.id, group.term.id); return; }
    const target = owner.processes.find(item => termKey(item) === id);
    if (target) {
      const parent = subsystem?.processes.some(item => item.id === target.id) ? subsystem : owner.subsystems.find(item => item.processes.some(candidate => candidate.id === target.id));
      navigate(owner.term.id, parent?.term.id, target.id);
    }
  }
  usePublishOntologySystemTree(Boolean(!loading && !error && graph.nodes.length && (!requestedSystem || system) && !processId && (!subsystemId || subsystem)), {
    nodes: graph?.nodes || [], edges: graph?.edges || [], selectedNodeId: selectedNode?.id || null,
    onSelect: selectNode, onOpen: selectNode, canOpen: id => Boolean(graph?.nodes.some(node => node.id === id)), openLabel: 'Inspect',
  });

  if (loading) return <p className="ontology-system-message" role="status">Loading systems…</p>;
  if (error) return <p className="ontology-system-message" role="alert">{error}</p>;
  if (!visibleSystems.length || (requestedSystem && !system)) return <section className="ontology-system-message"><h1>System</h1><p>{requestedSystem ? 'This system is no longer available in this selection.' : selectedSystems(query).length ? 'No selected systems are available in this workspace.' : 'No system overview is declared in the workspace ontologies.'}</p>{(requestedSystem || selectedSystems(query).length > 0) && <button type="button" onClick={() => router.push(`?${systemFilterRoute(query, [])}`, {scroll: false})}>Show available systems</button>}</section>;
  const unavailable = (!!subsystemId && !subsystem) || (!!processId && !process);
  return <section className="ontology-system-view" aria-label="System view">
    <div className="ontology-system-toolbar">
      {system && <><label>Subsystem<select aria-label="Subsystem" value={subsystem?.term.id || ''} onChange={event => navigate(system.term.id, event.target.value)}>
        <option value="">All subsystems</option>{system.subsystems.map(group => <option key={group.term.id} value={group.term.id}>{group.term.name.replace(/ processes$/, '')}</option>)}
      </select></label>
      <label>Process<select aria-label="Process" value={process?.id || ''} disabled={!processes.length} onChange={event => navigate(system.term.id, subsystem?.term.id, event.target.value)}>
        <option value="">All processes</option>{processes.map(term => <option key={term.id} value={term.id}>{systemProcessLabel(term)}</option>)}
      </select></label></>}
      <span className="ontology-system-count" aria-live="polite">{process ? systemProcessLabel(process) : `${subsystem ? subsystem.term.name.replace(/ processes$/, '') : system ? 'All subsystems' : `${visibleSystems.length} systems`} · ${processCount} processes`}</span>
    </div>
    {partial && <p className="ontology-system-notice" role="status">Some workspace files could not be read. This overview may be incomplete.</p>}
    {unavailable ? <div className="ontology-system-message"><p>This selection is not available in the current file filter.</p><button type="button" onClick={() => navigate(system?.term.id)}>Show available processes</button></div>
      : !processCount ? <p className="ontology-system-message">No processes in the selected files. Change the ontology checkboxes in the sidebar.</p>
      : process ? <OntologyTermNetwork key={process.id} term={process} terms={terms} systemSidebar />
      : <>
        <div className="ontology-system-body" onKeyDown={event => { if (event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); setSelected(null); } }}>
        <div className="ontology-system-canvas">
          <div className="ontology-system-viewport">
            <VisNetwork zoomOnDoubleClick key={graphKey} spacingKey={spacing.value} minimumAutoFitScale={1} nodes={canvasNodes} edges={graph.edges} selectedNodeId={selectedNode?.id || null}
              onNodeSelect={selectNode} onEdgeSelect={() => setSelected(null)} onNodeDoubleClick={drill}
              orthogonalEdges={params?.get('connectors') !== 'curved'} fixedLayout systemOverview fillContainer physicsEnabled={false} preserveZoomOnResize preserveZoomOnSelection focusOnSelection focusRequestKey={focusRequestKey}
              viewStateKey={`ontology:system:${graphKey}`} />
          </div>
        </div>
        {selectedNode && <OntologyNodeInspector node={selectedNode} nodes={graph.nodes} edges={graph.edges} terms={terms}
          onClose={() => setSelected(null)} onSelect={selectNode} onFocus={() => selectNode(selectedNode.id)}
          onOpenFullPage={target => router.push(`?${termRoute(query, target)}`, { scroll: false })}
          onExplore={selectedTerm ? () => drill(selectedNode.id) : undefined}
          exploreLabel={selectedNode.properties.system_level === 'process' ? 'Explore process' : selectedNode.properties.system_level === 'subsystem' ? 'Explore subsystem' : 'All subsystems'} />}
        </div>
        <div className="ontology-system-status" aria-live="polite">
          <span>{subsystem ? `${processes.length} processes` : `${system ? system.subsystems.length + ' subsystems' : visibleSystems.length + ' systems'} · ${processCount} processes`}</span>
        </div>
      </>}
  </section>;
}
