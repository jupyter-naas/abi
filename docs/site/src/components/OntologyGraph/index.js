import React, { useEffect, useRef } from 'react';

const C = (bg, bd) => ({ background: bg, border: bd, highlight: { background: bg, border: bd }, hover: { background: bg, border: bd } });

// Ontology hierarchy: BFO → CCO → ABI foundries + User ontologies
const NODES = [
  {
    id: 'bfo',
    label: 'BFO\nBasic Formal Ontology (ISO 21838-2)',
    x: 0, y: -280,
    color: C('#f1f5f9', '#475569'),
  },
  {
    id: 'cco',
    label: 'CCO\nCommon Core Ontologies',
    x: 0, y: -160,
    color: C('#e2e8f0', '#475569'),
  },
  {
    id: 'em',
    label: 'Enterprise Management Foundry\nOrgs · Persons · Products · Markets\nABI built-in',
    x: -280, y: 0,
    color: C('#dcfce7', '#22c55e'),
  },
  {
    id: 'personal',
    label: 'Personal AI Foundry\nPerson-centric knowledge\nABI built-in',
    x: 100, y: 0,
    color: C('#dcfce7', '#22c55e'),
  },
  {
    id: 'user-domain',
    label: 'Your Domain Ontologies\nBuilt in modules',
    x: -280, y: 180,
    color: C('#ede9fe', '#8b5cf6'),
  },
  {
    id: 'user-app',
    label: 'Your Application Ontologies\nBuilt in modules',
    x: 100, y: 180,
    color: C('#ede9fe', '#8b5cf6'),
  },
];

const EDGES = [
  { from: 'bfo', to: 'cco', label: 'foundation for', color: { color: '#94a3b8' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'cco', to: 'em', label: 'extends', color: { color: '#22c55e' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'cco', to: 'personal', label: 'extends', color: { color: '#22c55e' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'em', to: 'user-domain', label: 'your modules extend', dashes: true, color: { color: '#8b5cf6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'personal', to: 'user-app', label: 'your modules extend', dashes: true, color: { color: '#8b5cf6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
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

export default function OntologyGraph() {
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
        font: {
          size: 12,
          color: '#1e293b',
          face: 'ui-sans-serif, system-ui, sans-serif',
          multi: true,
        },
        borderWidth: 2,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 6, x: 0, y: 2 },
        widthConstraint: { minimum: 210, maximum: 260 },
      })));

      const edges = new DataSet(EDGES.map((e, i) => ({ id: i, ...e })));
      network = new Network(containerRef.current, { nodes, edges }, OPTIONS);
      network.fit({ animation: false });
    })();
    return () => network?.destroy();
  }, []);

  const legend = [
    { color: '#f1f5f9', border: '#475569', label: 'ISO open standard (external)' },
    { color: '#dcfce7', border: '#22c55e', label: 'ABI built-in foundry' },
    { color: '#ede9fe', border: '#8b5cf6', label: 'Your ontologies (in modules)' },
  ];

  return (
    <div style={{ margin: '24px 0' }}>
      <div
        ref={containerRef}
        style={{ height: '500px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#fafafa', overflow: 'hidden' }}
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
