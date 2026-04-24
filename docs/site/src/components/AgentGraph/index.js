import React, { useEffect, useRef } from 'react';

const C = (bg, bd) => ({ background: bg, border: bd, highlight: { background: bg, border: bd }, hover: { background: bg, border: bd } });

const NODES = [
  {
    id: 'abi',
    label: 'AbiAgent\nRoot supervisor · intent routing',
    x: 0, y: -220,
    color: C('#1e3a5f', '#1e40af'),
    font: { color: '#ffffff', size: 13, bold: true, face: 'ui-sans-serif, system-ui, sans-serif', multi: true },
  },
  { id: 'content',  label: 'ContentAgent\nLinkedIn tools',               x: -420, y:  10 },
  { id: 'crm',      label: 'CRMAgent\nSalesforce + knowledge graph',      x: -140, y:  10 },
  { id: 'finance',  label: 'FinanceAgent\nQuickBooks + SPARQL workflows', x:  140, y:  10 },
  { id: 'research', label: 'ResearchAgent\nWeb search + sub-agents',      x:  420, y:  10 },
  {
    id: 'onteng',
    label: 'OntologyEngineerAgent\nscope: research',
    x: 420, y: 230,
    color: C('#f8fafc', '#94a3b8'),
    borderDashes: [5, 4],
  },
];

const EDGES = [
  { from: 'abi', to: 'content',  label: 'routes', color: { color: '#3b82f6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'abi', to: 'crm',      label: 'routes', color: { color: '#3b82f6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'abi', to: 'finance',  label: 'routes', color: { color: '#3b82f6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'abi', to: 'research', label: 'routes', color: { color: '#3b82f6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'research', to: 'onteng', label: 'delegates to', dashes: true, color: { color: '#94a3b8' }, font: { size: 10, color: '#64748b', align: 'middle' } },
];

const OPTIONS = {
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false },
  edges: {
    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
    width: 1.8,
    smooth: { enabled: true, type: 'cubicBezier', roundness: 0.3 },
    font: { strokeWidth: 3, strokeColor: '#ffffff' },
  },
};

const defaultColor = C('#dbeafe', '#3b82f6');

export default function AgentGraph() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;

      const nodes = new DataSet(NODES.map(n => ({
        ...n,
        shape: 'box',
        color: n.color || defaultColor,
        margin: { top: 10, bottom: 10, left: 14, right: 14 },
        font: n.font || {
          size: 12,
          color: '#1e293b',
          face: 'ui-sans-serif, system-ui, sans-serif',
          multi: true,
        },
        borderWidth: 2,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 6, x: 0, y: 2 },
        widthConstraint: { minimum: 170, maximum: 210 },
      })));

      const edges = new DataSet(EDGES.map((e, i) => ({ id: i, ...e })));
      network = new Network(containerRef.current, { nodes, edges }, OPTIONS);
      network.fit({ animation: false });
    })();
    return () => network?.destroy();
  }, []);

  const legend = [
    { color: '#1e3a5f', border: '#1e40af', label: 'Supervisor (scope: supervisor)' },
    { color: '#dbeafe', border: '#3b82f6', label: 'Domain agent (scope: supervisor)' },
    { color: '#f8fafc', border: '#94a3b8', label: 'Dashed border: scope: research' },
  ];

  return (
    <div style={{ margin: '24px 0' }}>
      <div
        ref={containerRef}
        style={{ height: '460px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#fafafa', overflow: 'hidden' }}
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
