'use client';

import { useEffect, useMemo, useRef } from 'react';
import { ArrowUpRight, X } from 'lucide-react';
import type { GraphNode, GraphEdge } from '@/stores/knowledge-graph';
import { dictionaryKindLabel, type DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { BFO_BUCKET_BY_TYPE } from '@/lib/bfo-buckets';
import { inspectorTerm, inspectorConnections, inspectorSources } from '@/lib/ontology-node-inspector';
import { OntologyIconPicker } from './ontology-icon-picker';
import './ontology-node-inspector.css';

export function OntologyNodeInspector({ node, nodes, edges, terms, context, onClose, onSelect, onOpenFullPage, onFocus, onExplore, exploreLabel }: {
  node: GraphNode;
  nodes: GraphNode[];
  edges: GraphEdge[];
  terms: DictionaryTerm[];
  context?: DictionaryTerm;
  onClose: () => void;
  onSelect: (id: string) => void;
  onOpenFullPage: (term: DictionaryTerm) => void;
  onFocus?: () => void;
  onExplore?: () => void;
  exploreLabel?: string;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const term = useMemo(() => inspectorTerm(node, terms), [node, terms]);
  const connections = useMemo(() => inspectorConnections(node, nodes, edges), [node, nodes, edges]);
  const sources = useMemo(() => inspectorSources(node, term), [node, term]);
  const ledger = node.properties.presentation_only === true;
  const bucket = ledger ? String(node.properties.ledger_bucket || '') : BFO_BUCKET_BY_TYPE[node.type]?.label;
  const kind = ledger ? 'Ledger entry' : term ? dictionaryKindLabel(term.type) : String(node.properties.kind || 'Referenced term');
  const definition = term?.description || (!ledger ? String(node.properties.definition || '') : '');
  const uri = term?.id || (typeof node.properties.iri === 'string' ? node.properties.iri : undefined);
  useEffect(() => {
    const previous = document.activeElement;
    heading.current?.focus({ preventScroll: true });
    return () => { if (previous instanceof HTMLElement && previous.isConnected) previous.focus({ preventScroll: true }); };
  }, []);

  useEffect(() => { if (content.current) content.current.scrollTop = 0; }, [node.id]);

  return <aside className="ontology-node-inspector" aria-label={`${node.label} inspector`} onKeyDown={event => {
    if (event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); event.stopPropagation(); onClose(); }
  }}>
    <header className="ontology-node-inspector-header">
      <div>
        <OntologyIconPicker subject={term || { name: node.label }} className="ontology-node-inspector-topic-icon" />
        <p className="ontology-node-inspector-kind"><span style={{ backgroundColor: node.color || BFO_BUCKET_BY_TYPE[node.type]?.color }} />{bucket ? `${bucket} · ` : ''}{kind}</p>
        <h2 ref={heading} tabIndex={-1}>{node.label}</h2>
        {uri ? <p className="ontology-node-inspector-uri">{uri}</p> : null}
      </div>
      <button type="button" className="ontology-node-inspector-close" aria-label="Close inspector" onClick={onClose}><X size={15} /></button>
    </header>
    <div ref={content} className="ontology-node-inspector-content">
      {definition && <section><h3>Definition</h3><p>{definition}</p></section>}
      {context && context.id !== term?.id && <section><h3>In process</h3><p>{context.processLedger?.code ? `${context.processLedger.code} · ` : ''}{context.name}</p></section>}
      {ledger && term && <section><h3>Ontology term</h3><p>{term.name}</p></section>}
      {connections.length > 0 && <section>
        <h3>{ledger ? 'Ledger connections' : 'Connections in this view'} <span>{connections.length}</span></h3>
        <ul className="ontology-node-inspector-connections">{connections.map(({ edge, other, incoming }) => <li key={edge.id}>
          <button type="button" onClick={() => onSelect(other.id)} title={`Inspect ${other.label}`}>
            <span>{incoming ? `${other.label} → ${edge.label || edge.type} → ${node.label}` : `${node.label} → ${edge.label || edge.type} → ${other.label}`}</span>
            <ArrowUpRight size={12} />
          </button>
        </li>)}</ul>
      </section>}
      {sources.length > 0 && <section><h3>{sources.length === 1 ? 'Source' : 'Sources'}</h3><ul className="ontology-node-inspector-sources">{sources.map(source => <li key={source.path} title={source.path}>{source.path.split('/').pop() || source.name}</li>)}</ul></section>}
    </div>
    <footer className="ontology-node-inspector-actions">
      {onFocus && <button type="button" onClick={onFocus}>Focus node</button>}
      {term ? <button type="button" onClick={() => onOpenFullPage(term)}>Open full page <ArrowUpRight size={13} /></button>
        : ledger && context ? <button type="button" onClick={() => onOpenFullPage(context)}>Open process page <ArrowUpRight size={13} /></button> : null}
      {onExplore && <button type="button" onClick={onExplore}>{exploreLabel || 'Explore connections'}</button>}
    </footer>
  </aside>;
}
