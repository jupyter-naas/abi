import React, { useEffect, useRef } from 'react';

// Two-row layout: ingest path on top, query path on bottom, KG in the middle-right bridging both.
const NODES = [
  // ── INGEST ROW (y = -120) ──────────────────────────────────────
  {
    id: 'ext',
    label: 'External Services\nGitHub · LinkedIn · Salesforce\nGmail · Stripe · ...',
    x: -540, y: -120,
    color: { background: '#f8fafc', border: '#94a3b8', highlight: { background: '#f1f5f9', border: '#94a3b8' }, hover: { background: '#f1f5f9', border: '#94a3b8' } },
  },
  {
    id: 'int',
    label: 'Integrations\nRead connectors',
    x: -240, y: -120,
    color: { background: '#fff7ed', border: '#f97316', highlight: { background: '#ffedd5', border: '#f97316' }, hover: { background: '#ffedd5', border: '#f97316' } },
  },
  {
    id: 'pipe',
    label: 'Pipelines\nOWL/RDF transforms',
    x: 60, y: -120,
    color: { background: '#fef9c3', border: '#eab308', highlight: { background: '#fef08a', border: '#eab308' }, hover: { background: '#fef08a', border: '#eab308' } },
  },
  {
    id: 'kg',
    label: 'Knowledge Graph\nTriple Store  (SPARQL)',
    x: 380, y: -120,
    color: { background: '#fef3c7', border: '#d97706', highlight: { background: '#fde68a', border: '#d97706' }, hover: { background: '#fde68a', border: '#d97706' } },
  },

  // ── QUERY ROW (y = +120) ───────────────────────────────────────
  {
    id: 'tools',
    label: 'SPARQL Tools\nTemplatableSparqlQuery',
    x: 380, y: 120,
    color: { background: '#ede9fe', border: '#8b5cf6', highlight: { background: '#ddd6fe', border: '#8b5cf6' }, hover: { background: '#ddd6fe', border: '#8b5cf6' } },
  },
  {
    id: 'wf',
    label: 'Workflows\nBusiness logic',
    x: 80, y: 120,
    color: { background: '#dbeafe', border: '#3b82f6', highlight: { background: '#bfdbfe', border: '#3b82f6' }, hover: { background: '#bfdbfe', border: '#3b82f6' } },
  },
  {
    id: 'agents',
    label: 'Agents\nLLM-powered router',
    x: -220, y: 120,
    color: { background: '#fef9c3', border: '#eab308', highlight: { background: '#fef08a', border: '#eab308' }, hover: { background: '#fef08a', border: '#eab308' } },
  },
  {
    id: 'apps',
    label: 'Apps\nREST API · MCP · Nexus',
    x: -440, y: 120,
    color: { background: '#d1fae5', border: '#22c55e', highlight: { background: '#a7f3d0', border: '#22c55e' }, hover: { background: '#a7f3d0', border: '#22c55e' } },
  },
  {
    id: 'users',
    label: 'Users & Callers',
    x: -640, y: 120,
    color: { background: '#f8fafc', border: '#94a3b8', highlight: { background: '#f1f5f9', border: '#94a3b8' }, hover: { background: '#f1f5f9', border: '#94a3b8' } },
  },
];

function mkNode(n) {
  return {
    ...n,
    shape: 'box',
    margin: { top: 8, bottom: 8, left: 12, right: 12 },
    font: { size: 12, color: '#1e293b', face: 'ui-sans-serif, system-ui, sans-serif', multi: false },
    borderWidth: 2,
    borderWidthSelected: 3,
    shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 6, x: 0, y: 2 },
    widthConstraint: { minimum: 140, maximum: 200 },
  };
}

function edge(from, to, opts = {}) {
  return { from, to, ...opts };
}

const EDGES = [
  // Ingest path (orange)
  edge('ext',  'int',  { label: 'raw data',       color: { color: '#f97316', highlight: '#ea580c', hover: '#ea580c' }, font: { size: 10, color: '#f97316', align: 'middle' } }),
  edge('int',  'pipe', { label: 'normalize',       color: { color: '#f97316', highlight: '#ea580c', hover: '#ea580c' }, font: { size: 10, color: '#f97316', align: 'middle' } }),
  edge('pipe', 'kg',   { label: 'OWL/RDF triples', color: { color: '#d97706', highlight: '#b45309', hover: '#b45309' }, font: { size: 10, color: '#d97706', align: 'middle' } }),

  // Bridge: KG → Tools (vertical, purple)
  edge('kg', 'tools', { label: 'graph context', color: { color: '#8b5cf6', highlight: '#7c3aed', hover: '#7c3aed' }, font: { size: 10, color: '#8b5cf6', align: 'middle' } }),

  // Query path (blue/purple, right to left)
  edge('tools',  'wf',     { color: { color: '#3b82f6', highlight: '#2563eb', hover: '#2563eb' } }),
  edge('wf',     'agents', { color: { color: '#3b82f6', highlight: '#2563eb', hover: '#2563eb' } }),
  edge('agents', 'apps',   { color: { color: '#22c55e', highlight: '#16a34a', hover: '#16a34a' } }),
  edge('apps',   'users',  { label: 'response',   color: { color: '#22c55e', highlight: '#16a34a', hover: '#16a34a' }, font: { size: 10, color: '#22c55e', align: 'middle' } }),

  // User request (reverse, dashed)
  edge('users', 'apps', { dashes: true, label: 'request', color: { color: '#94a3b8', highlight: '#64748b', hover: '#64748b' }, font: { size: 10, color: '#94a3b8', align: 'middle' } }),

  // Feedback: Workflows → Integrations for write operations (dashed)
  edge('wf', 'int', { dashes: true, label: 'write ops', color: { color: '#94a3b8', highlight: '#64748b', hover: '#64748b' }, font: { size: 10, color: '#64748b', align: 'middle' }, smooth: { type: 'curvedCCW', roundness: 0.4 } }),
];

const OPTIONS = {
  layout: { randomSeed: 0 },
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false, tooltipDelay: 150 },
  edges: {
    arrows: { to: { enabled: true, scaleFactor: 0.55 } },
    width: 1.8,
    smooth: { enabled: true, type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.3 },
    font: { strokeWidth: 3, strokeColor: '#ffffff' },
  },
  nodes: { widthConstraint: { maximum: 200 } },
};

const LEGEND = [
  { color: '#f97316', label: 'Ingest path' },
  { color: '#8b5cf6', label: 'Graph context' },
  { color: '#3b82f6', label: 'Query path' },
  { color: '#22c55e', label: 'Response' },
  { color: '#94a3b8', label: 'Request / writes (dashed)' },
];

export default function DataFlowGraph() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;

      const nodes = new DataSet(NODES.map(mkNode));
      const edges = new DataSet(EDGES.map((e, i) => ({ id: i, ...e })));
      network = new Network(containerRef.current, { nodes, edges }, OPTIONS);
      network.fit({ animation: false });
    })();
    return () => network?.destroy();
  }, []);

  return (
    <div style={{ margin: '24px 0' }}>
      <div
        ref={containerRef}
        style={{ height: '340px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff', overflow: 'hidden' }}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', marginTop: '10px', justifyContent: 'center' }}>
        {LEGEND.map(({ color, label }) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.75rem', color: '#64748b' }}>
            <span style={{ width: 22, height: 3, background: color, borderRadius: '2px', flexShrink: 0 }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
