import React, { useEffect, useRef } from 'react';

// Diamond layout: cli at top, naas-abi left, marketplace right, core at bottom
const NODES = [
  {
    id: 'cli',
    label: 'naas-abi-cli\nabi stack · abi chat · abi deploy',
    x: 0, y: -160,
    color: { background: '#d1fae5', border: '#22c55e', highlight: { background: '#a7f3d0', border: '#22c55e' }, hover: { background: '#a7f3d0', border: '#22c55e' } },
  },
  {
    id: 'abi',
    label: 'naas-abi\nAgents · Nexus · Pipelines · Modules',
    x: -240, y: 0,
    color: { background: '#dbeafe', border: '#3b82f6', highlight: { background: '#bfdbfe', border: '#3b82f6' }, hover: { background: '#bfdbfe', border: '#3b82f6' } },
  },
  {
    id: 'mkt',
    label: 'naas-abi-marketplace\nCommunity integrations & agents',
    x: 240, y: 0,
    color: { background: '#ede9fe', border: '#8b5cf6', highlight: { background: '#ddd6fe', border: '#8b5cf6' }, hover: { background: '#ddd6fe', border: '#8b5cf6' } },
  },
  {
    id: 'core',
    label: 'naas-abi-core\nEngine · Services · Module runtime',
    x: 0, y: 160,
    color: { background: '#fce7f3', border: '#ec4899', highlight: { background: '#fbcfe8', border: '#ec4899' }, hover: { background: '#fbcfe8', border: '#ec4899' } },
  },
];

const EDGES = [
  { from: 'cli', to: 'abi',  label: 'orchestrates', color: { color: '#3b82f6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'cli', to: 'mkt',  label: 'loads modules', dashes: true, color: { color: '#8b5cf6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'abi', to: 'core', label: 'imports', color: { color: '#ec4899' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'abi', to: 'mkt',  label: 'enables selectively', dashes: true, color: { color: '#8b5cf6' }, font: { size: 10, color: '#64748b', align: 'middle' } },
  { from: 'mkt', to: 'core', label: 'imports', color: { color: '#ec4899' }, font: { size: 10, color: '#64748b', align: 'middle' } },
];

const OPTIONS = {
  layout: { randomSeed: 0 },
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false },
  edges: {
    arrows: { to: { enabled: true, scaleFactor: 0.55 } },
    width: 1.8,
    smooth: { enabled: true, type: 'cubicBezier', roundness: 0.3 },
    font: { strokeWidth: 3, strokeColor: '#ffffff' },
  },
  nodes: { widthConstraint: { maximum: 240 } },
};

export default function PackageDiagram() {
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
        font: { size: 13, color: '#1e293b', face: 'ui-sans-serif, system-ui, sans-serif' },
        borderWidth: 2,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 6, x: 0, y: 2 },
        widthConstraint: { minimum: 200, maximum: 260 },
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
        style={{ height: '380px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff', overflow: 'hidden' }}
      />
    </div>
  );
}
