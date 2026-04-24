import React, { useEffect, useRef } from 'react';

const C = (bg, bd) => ({ background: bg, border: bd, highlight: { background: bg, border: bd }, hover: { background: bg, border: bd } });

// Hub layout: Knowledge Graph at center, four peripheral nodes
const NODES = [
  {
    id: 'kg',
    label: 'Knowledge Graph\nRDF / OWL / SPARQL',
    x: 0, y: 0,
    color: C('#1e3a5f', '#1e40af'),
    font: { color: '#ffffff', size: 13, bold: true, face: 'ui-sans-serif, system-ui, sans-serif', multi: true },
    widthConstraint: { minimum: 180, maximum: 200 },
  },
  {
    id: 'data',
    label: 'Data Sources\nCRM · ERP · APIs · Files',
    x: -300, y: -160,
    color: C('#dbeafe', '#3b82f6'),
  },
  {
    id: 'integrations',
    label: 'Integrations\nGitHub · LinkedIn · Stripe · ...',
    x: 300, y: -160,
    color: C('#dbeafe', '#3b82f6'),
  },
  {
    id: 'agents',
    label: 'Agents\nLLM · intent routing · tools',
    x: -300, y: 160,
    color: C('#dcfce7', '#22c55e'),
  },
  {
    id: 'pipelines',
    label: 'Pipelines & Workflows\nDagster · event-driven · scheduled',
    x: 300, y: 160,
    color: C('#dcfce7', '#22c55e'),
  },
];

const ef = (color) => ({ size: 10, color: '#64748b', align: 'middle', strokeWidth: 2, strokeColor: '#ffffff' });

const EDGES = [
  { from: 'data',         to: 'kg',         label: 'ingest as RDF triples',  arrows: 'to',   color: { color: '#60a5fa' }, font: ef() },
  { from: 'integrations', to: 'kg',         label: 'sync external APIs',      arrows: 'to',   color: { color: '#60a5fa' }, font: ef() },
  { from: 'kg',           to: 'agents',     label: 'SPARQL queries + reason', arrows: 'to',   color: { color: '#86efac' }, font: ef() },
  { from: 'agents',       to: 'kg',         label: 'write back facts',        arrows: 'to',   color: { color: '#86efac' }, font: ef() },
  { from: 'kg',           to: 'pipelines',  label: 'query + transform',       arrows: 'to',   color: { color: '#86efac' }, font: ef() },
  { from: 'pipelines',    to: 'kg',         label: 'write triples',           arrows: 'to',   color: { color: '#86efac' }, font: ef() },
];

const OPTIONS = {
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false },
  edges: {
    width: 1.8,
    smooth: { enabled: true, type: 'cubicBezier', roundness: 0.35 },
    font: { strokeWidth: 2, strokeColor: '#ffffff' },
  },
};

export default function CoreIdeaGraph() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;

      const nodes = new DataSet(NODES.map(n => ({
        ...n,
        shape: 'box',
        margin: { top: 10, bottom: 10, left: 14, right: 14 },
        font: n.font || {
          size: 12,
          color: '#1e293b',
          face: 'ui-sans-serif, system-ui, sans-serif',
          multi: true,
        },
        borderWidth: 2,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 6, x: 0, y: 2 },
        widthConstraint: n.widthConstraint || { minimum: 190, maximum: 220 },
      })));

      const edges = new DataSet(EDGES.map((e, i) => ({ id: i, ...e })));
      network = new Network(containerRef.current, { nodes, edges }, OPTIONS);
      network.fit({ animation: false });
    })();
    return () => network?.destroy();
  }, []);

  const legend = [
    { color: '#1e3a5f', border: '#1e40af', label: 'Knowledge Graph (shared source of truth)' },
    { color: '#dbeafe', border: '#3b82f6', label: 'Data inputs' },
    { color: '#dcfce7', border: '#22c55e', label: 'Consumers and writers' },
  ];

  return (
    <div style={{ margin: '24px 0' }}>
      <div
        ref={containerRef}
        style={{ height: '420px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#fafafa', overflow: 'hidden' }}
      />
      <div style={{ display: 'flex', gap: '20px', marginTop: '10px', flexWrap: 'wrap', fontSize: '12px', color: '#64748b' }}>
        {legend.map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: 14, height: 14, borderRadius: 3, background: l.color, border: `2px solid ${l.border}`, flexShrink: 0 }} />
            {l.label}
          </div>
        ))}
      </div>
    </div>
  );
}
