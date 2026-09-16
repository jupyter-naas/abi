'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { buildOntologySystems, buildSystemGraph, systemProcessLabel } from '@/lib/ontology-system-graph';
import { dictionaryFiles, filterTermsByFiles } from '@/lib/ontology-file-filter';
import { systemRoute } from '@/lib/ontology-navigation';
import { termKey } from '@/lib/ontology-context';
import { OntologyTermNetwork } from './ontology-term-network';
import { buildHoverTitle } from '@/components/graph/vis-network';
import type { GraphNode } from '@/stores/knowledge-graph';
import { usePublishOntologySystemTree } from '@/hooks/use-ontology-system-tree';
import './ontology-system-view.css';

const VisNetwork = dynamic(() => import('@/components/graph/vis-network').then(module => module.VisNetwork), { ssr: false });
const getNodeTitle = (node: GraphNode) => buildHoverTitle([
  ['Name', node.label], ['Definition', String(node.properties.definition || '')],
  ['Navigate', 'Double-click to open'],
]);

export function OntologySystemView({ terms, loading, error, partial }: { terms: DictionaryTerm[]; loading: boolean; error: string | null; partial: boolean }) {
  const router = useRouter(); const params = useSearchParams();
  const query = params?.toString() || '';
  const models = useMemo(() => buildOntologySystems(terms, filterTermsByFiles(terms, dictionaryFiles(query))), [terms, query]);
  const requestedSystem = params?.get('system');
  const system = models.find(model => model.term.id === requestedSystem) || (!requestedSystem ? models[0] : undefined);
  const subsystemId = params?.get('subsystem') || '';
  const processId = params?.get('process') || '';
  const subsystem = system?.subsystems.find(group => group.term.id === subsystemId);
  const processes = subsystem?.processes || system?.processes || [];
  const process = processes.find(term => term.id === processId);
  const graph = useMemo(() => system ? buildSystemGraph(system, subsystemId) : null, [system, subsystemId]);
  const [selected, setSelected] = useState<string | null>(null);
  const selectedNode = graph?.nodes.find(node => node.id === selected);
  const selectedTerm = terms.find(term => termKey(term) === selectedNode?.id);
  const navigate = (systemId?: string, groupId?: string, termId?: string) => {
    setSelected(null);
    router.push(`?${systemRoute(query, systemId, groupId, termId)}`, { scroll: false });
  };
  function drill(id: string) {
    if (!system || !graph) return;
    if (id === termKey(system.term)) { navigate(system.term.id); return; }
    const group = system.subsystems.find(item => termKey(item.term) === id);
    if (group) { navigate(system.term.id, group.term.id); return; }
    const target = system.processes.find(item => termKey(item) === id);
    if (target) {
      const parent = subsystem?.processes.some(item => item.id === target.id) ? subsystem : system.subsystems.find(item => item.processes.some(candidate => candidate.id === target.id));
      navigate(system.term.id, parent?.term.id, target.id);
    }
  }
  usePublishOntologySystemTree(Boolean(!loading && !error && system?.processes.length && graph && !processId && (!subsystemId || subsystem)), {
    nodes: graph?.nodes || [], edges: graph?.edges || [], selectedNodeId: selectedNode?.id || null,
    onSelect: setSelected, onOpen: drill, canOpen: id => Boolean(graph?.nodes.some(node => node.id === id)), openLabel: 'Open',
  });

  if (loading) return <p className="ontology-system-message" role="status">Loading systems…</p>;
  if (error) return <p className="ontology-system-message" role="alert">{error}</p>;
  if (!system || !graph) return <section className="ontology-system-message"><h1>System</h1><p>{requestedSystem ? 'This system is no longer available in this workspace.' : 'No system overview is declared in the workspace ontologies.'}</p>{requestedSystem && <button type="button" onClick={() => navigate()}>Show available systems</button>}</section>;
  const unavailable = (!!subsystemId && !subsystem) || (!!processId && !process);
  return <section className="ontology-system-view" aria-label="System view">
    <div className="ontology-system-toolbar">
      {models.length > 1 && <label>System<select aria-label="System" value={system.term.id} onChange={event => navigate(event.target.value)}>{models.map(model => <option key={model.term.id} value={model.term.id}>{model.term.name}</option>)}</select></label>}
      <label>Subsystem<select aria-label="Subsystem" value={subsystem?.term.id || ''} onChange={event => navigate(system.term.id, event.target.value)}>
        <option value="">All subsystems</option>{system.subsystems.map(group => <option key={group.term.id} value={group.term.id}>{group.term.name.replace(/ processes$/, '')}</option>)}
      </select></label>
      <label>Process<select aria-label="Process" value={process?.id || ''} disabled={!subsystem && !process} onChange={event => navigate(system.term.id, subsystem?.term.id, event.target.value)}>
        <option value="">All processes</option>{processes.map(term => <option key={term.id} value={term.id}>{systemProcessLabel(term)}</option>)}
      </select></label>
      <span className="ontology-system-count" aria-live="polite">{process ? systemProcessLabel(process) : `${subsystem ? subsystem.term.name.replace(/ processes$/, '') : 'All subsystems'} · ${processes.length} processes`}</span>
    </div>
    {partial && <p className="ontology-system-notice" role="status">Some workspace files could not be read. This overview may be incomplete.</p>}
    {unavailable ? <div className="ontology-system-message"><p>This selection is not available in the current file filter.</p><button type="button" onClick={() => navigate(system.term.id)}>Show available processes</button></div>
      : !system.processes.length ? <p className="ontology-system-message">No processes in the selected files. Change the Files checkboxes in the sidebar.</p>
      : process ? <OntologyTermNetwork key={process.id} term={process} terms={terms} systemSidebar />
      : <>
        <div className="ontology-system-canvas">
          <div className="ontology-system-viewport">
            <VisNetwork key={`${system.term.id}:${subsystemId}`} nodes={graph.nodes} edges={graph.edges} selectedNodeId={selectedNode?.id || null}
              onNodeSelect={setSelected} onEdgeSelect={() => setSelected(null)} onNodeDoubleClick={drill}
              fixedLayout systemOverview fillContainer physicsEnabled={false} getNodeTitle={getNodeTitle}
              viewStateKey={`ontology:system:${system.term.id}:${subsystemId}`} />
          </div>
        </div>
        <div className="ontology-system-status" aria-live="polite">
          {selectedNode ? <><span>{selectedNode.label}</span>{selectedTerm && <button type="button" onClick={() => drill(selectedNode.id)}>{selectedNode.properties.system_level === 'process' ? 'Open process' : selectedNode.properties.system_level === 'subsystem' ? 'Open subsystem' : 'All subsystems'}</button>}</>
            : <span>{subsystem ? `${processes.length} processes` : `${system.subsystems.length} subsystems · ${system.processes.length} processes`}</span>}
        </div>
      </>}
  </section>;
}
