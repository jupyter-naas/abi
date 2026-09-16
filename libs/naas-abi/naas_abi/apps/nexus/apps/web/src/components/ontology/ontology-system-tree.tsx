'use client';

import { useMemo, useState } from 'react';
import { ChevronRight, ArrowUpRight } from 'lucide-react';
import { useOntologySystemTreeStore } from '@/stores/ontology-system-tree';
import { useOntologySystemTreeScope } from '@/hooks/use-ontology-system-tree';
import { buildBucketTree, filterBucketTree, type BucketTreeNode } from '@/lib/ontology-bucket-tree';
import './ontology-system-tree.css';

export function OntologySystemTree({ query }: { query: string }) {
  const scope = useOntologySystemTreeScope();
  const current = useOntologySystemTreeStore(state => state.current);
  const graph = current?.scope === scope ? current : null;
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const tree = useMemo(() => graph ? filterBucketTree(buildBucketTree(graph.nodes, graph.edges), query) : [], [graph, query]);
  const searching = Boolean(query.trim());
  function toggle(id: string) {
    setClosed(previous => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }
  function renderNode(entry: BucketTreeNode) {
    const { node, children } = entry;
    const expanded = searching || !closed.has(node.id);
    const selected = graph?.selectedNodeId === node.id;
    const canOpen = graph?.canOpen(node.id);
    return <li key={node.id}>
      <div className="ontology-system-tree-row" data-selected={selected || undefined}>
        {children.length > 0 ? <button type="button" className="ontology-system-tree-disclosure" aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.label}`} aria-expanded={expanded} onClick={() => toggle(node.id)}>
          <ChevronRight size={12} className={expanded ? 'is-expanded' : undefined} />
        </button> : <span className="ontology-system-tree-spacer" />}
        <button type="button" className="ontology-system-tree-term" aria-pressed={selected}
          title={`${node.label}\n${node.properties.definition || ''}`} onClick={() => graph?.onSelect(node.id)} onDoubleClick={() => { if (canOpen) graph?.onOpen(node.id); }}>
          <span>{node.label}</span>
        </button>
        {canOpen && <button type="button" className="ontology-system-tree-open" aria-label={`${graph!.openLabel}: ${node.label}`} title={graph!.openLabel} onClick={() => graph?.onOpen(node.id)}><ArrowUpRight size={12} /></button>}
      </div>
      {expanded && children.length > 0 && <ul className="ontology-system-tree-children">{children.map(renderNode)}</ul>}
    </li>;
  }

  return <nav className="ontology-system-tree" aria-label="System by BFO bucket">
    <p className="ontology-system-tree-heading">BFO 7 buckets</p>
    {!graph ? <p className="ontology-system-tree-empty" role="status">No system graph to explore.</p>
      : !tree.length ? <p className="ontology-system-tree-empty" role="status">No matching elements.</p>
      : <ul>{tree.map(({ bucket, roots, count }) => {
        const key = `bucket:${bucket.type}`;
        const expanded = searching || !closed.has(key);
        return <li key={key}>
          <button type="button" className="ontology-system-tree-bucket" aria-expanded={roots.length ? expanded : undefined} disabled={!roots.length}
            title={`${bucket.type} · ${bucket.description}${!count ? '\nNo elements in this graph.' : ''}`} onClick={() => toggle(key)}>
            <ChevronRight size={12} className={expanded && roots.length ? 'is-expanded' : undefined} />
            <span className="ontology-system-tree-dot" style={{ backgroundColor: bucket.color }} />
            <span>{bucket.label}</span><span className="ontology-system-tree-count">{count}</span>
          </button>
          {expanded && roots.length > 0 && <ul className="ontology-system-tree-children">{roots.map(renderNode)}</ul>}
        </li>;
      })}</ul>}
  </nav>;
}
