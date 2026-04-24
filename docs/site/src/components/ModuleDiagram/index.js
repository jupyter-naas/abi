import React, { useEffect, useRef } from 'react';

// Radial layout: Module at center, 6 component types radiating out.
// Shows the anatomy of a single ABIModule unit.

const toRad = deg => (deg * Math.PI) / 180;
const at = (r, deg) => ({ x: Math.round(r * Math.cos(toRad(deg))), y: Math.round(r * Math.sin(toRad(deg))) });

const dark  = { background: '#1e293b', border: '#0f172a', highlight: { background: '#334155', border: '#0f172a' }, hover: { background: '#334155', border: '#0f172a' } };
const amber = { background: '#fef9c3', border: '#eab308', highlight: { background: '#fde68a', border: '#eab308' }, hover: { background: '#fde68a', border: '#eab308' } };
const blue  = { background: '#dbeafe', border: '#3b82f6', highlight: { background: '#bfdbfe', border: '#3b82f6' }, hover: { background: '#bfdbfe', border: '#3b82f6' } };
const purp  = { background: '#ede9fe', border: '#8b5cf6', highlight: { background: '#ddd6fe', border: '#8b5cf6' }, hover: { background: '#ddd6fe', border: '#8b5cf6' } };
const green = { background: '#d1fae5', border: '#22c55e', highlight: { background: '#a7f3d0', border: '#22c55e' }, hover: { background: '#a7f3d0', border: '#22c55e' } };
const orange = { background: '#fff7ed', border: '#f97316', highlight: { background: '#ffedd5', border: '#f97316' }, hover: { background: '#ffedd5', border: '#f97316' } };
const pink  = { background: '#fce7f3', border: '#ec4899', highlight: { background: '#fbcfe8', border: '#ec4899' }, hover: { background: '#fbcfe8', border: '#ec4899' } };

const POS = {
  module:       { x:    0, y:    0 },
  onto:         { x: -193, y: -179 },
  pipes:        { x: -276, y:  -71 },
  ints:         { x: -242, y:   71 },
  agts:         { x:  162, y: -180 },
  wfs:          { x:  281, y:  -64 },
  orch:         { x:  261, y:   71 },
  apps:         { x:   93, y:  177 },
  cfg:          { x:   -7, y: -255 },
  dep:          { x: -184, y:  191 },
  'lbl-data':   { x: -320, y:    0 },
  'lbl-product':{ x:  320, y:    0 },
};

const COMPONENTS = [
  { id: 'onto',  color: amber,  label: 'ontologies/\nOWL/Turtle schema\nauto-loaded on on_load()' },
  { id: 'pipes', color: green,  label: 'pipelines/\nIngest raw data\ninto the triple store' },
  { id: 'ints',  color: orange, label: 'integrations/\nExternal API connectors\nGitHub · LinkedIn · Stripe …' },
  { id: 'agts',  color: amber,  label: 'agents/\nLLM-powered agents\nreason over the KG' },
  { id: 'wfs',   color: blue,   label: 'workflows/\nSPARQL-backed tools\ninvoked by agents & users' },
  { id: 'orch',  color: purp,   label: 'orchestrations/\nScheduled tasks\nand sensors' },
  { id: 'apps',  color: green,  label: 'apps/\nCLI · Web · API\nper-module entry points' },
];

const LIFECYCLE = [
  { id: 'cfg', color: pink, label: 'ModuleConfiguration\nglobal_config + module settings' },
  { id: 'dep', color: pink, label: 'ModuleDependencies\nservices + other module paths' },
];

const LABELS = [
  { id: 'lbl-data',    label: '← Semantic Data',  color: { background: 'transparent', border: 'transparent', highlight: { background: 'transparent', border: 'transparent' }, hover: { background: 'transparent', border: 'transparent' } }, font: { color: '#94a3b8', size: 11, bold: true }, shape: 'text' },
  { id: 'lbl-product', label: 'AI Product →',     color: { background: 'transparent', border: 'transparent', highlight: { background: 'transparent', border: 'transparent' }, hover: { background: 'transparent', border: 'transparent' } }, font: { color: '#94a3b8', size: 11, bold: true }, shape: 'text' },
];

const NODES = [
  { id: 'module', label: 'ABIModule\nSemantic Data & AI Product', color: dark, font: { color: '#ffffff', size: 13 } },
  ...COMPONENTS.map(c => ({ id: c.id, label: c.label, color: c.color })),
  ...LIFECYCLE,
  ...LABELS,
].map(n => ({ ...n, ...POS[n.id] }));

const EDGES = [
  // Component edges (solid — loaded or wired by the module)
  ...COMPONENTS.map(c => ({ from: 'module', to: c.id })),
  // Config/deps edges (dashed — declared on the module class)
  { from: 'module', to: 'cfg', dashes: true },
  { from: 'module', to: 'dep', dashes: true },
  // No edges to label nodes
];

const OPTIONS = {
  layout: { randomSeed: 0 },
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false },
  edges: {
    arrows: { to: { enabled: false } },
    color: { color: '#cbd5e1', highlight: '#94a3b8', hover: '#94a3b8' },
    width: 1.8,
    smooth: { enabled: false },
  },
  nodes: { widthConstraint: { maximum: 230 } },
};

const LEGEND = [
  { color: '#eab308', label: 'Auto-loaded (on_load)' },
  { color: '#3b82f6', label: 'Workflow tools' },
  { color: '#22c55e', label: 'Data ingestion / Apps' },
  { color: '#f97316', label: 'External connectors' },
  { color: '#8b5cf6', label: 'Orchestration' },
  { color: '#ec4899', label: 'Config / deps (dashed)' },
];

export default function ModuleDiagram() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;
      const nodes = new DataSet(NODES.map(n => ({
        ...n,
        shape: n.shape || 'box',
        margin: { top: 9, bottom: 9, left: 12, right: 12 },
        font: { size: 12, face: 'ui-sans-serif, system-ui, sans-serif', color: '#1e293b', ...(n.font || {}) },
        borderWidth: 2,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 5, x: 0, y: 2 },
        widthConstraint: { minimum: 140, maximum: 230 },
      })));
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
        style={{ height: '580px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff', overflow: 'hidden' }}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', marginTop: '10px', justifyContent: 'center', alignItems: 'center' }}>
        {LEGEND.map(({ color, label }) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.75rem', color: '#64748b' }}>
            <span style={{ width: 10, height: 10, borderRadius: '2px', background: color, flexShrink: 0 }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
