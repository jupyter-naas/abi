import React, { useEffect, useRef } from 'react';

// Star layout: Engine at center, 6 service ports in a circle around it.
// Adapters listed in each port's label to keep the graph uncluttered.
const R = 260; // radius for port nodes
const ports = [
  { id: 'triple',  angle: -90, label: 'Triple Store\nFuseki TDB2 · Oxigraph\nNeptune · FS' },
  { id: 'vector',  angle: -30, label: 'Vector Store\nQdrant · in-memory' },
  { id: 'obj',     angle:  30, label: 'Object Storage\nMinIO / S3 · FS · Naas' },
  { id: 'bus',     angle:  90, label: 'Message Bus\nRabbitMQ · Python queue' },
  { id: 'kv',      angle: 150, label: 'KV + Cache\nRedis · in-memory · FS' },
  { id: 'secret',  angle: 210, label: 'Secret\ndotenv · Naas · Base64' },
];

const PORT_COLORS = [
  { background: '#fef9c3', border: '#eab308' },  // triple  - amber
  { background: '#dbeafe', border: '#3b82f6' },  // vector  - blue
  { background: '#d1fae5', border: '#22c55e' },  // object  - green
  { background: '#fff7ed', border: '#f97316' },  // bus     - orange
  { background: '#ede9fe', border: '#8b5cf6' },  // kv      - purple
  { background: '#fce7f3', border: '#ec4899' },  // secret  - pink
];

const toRad = deg => (deg * Math.PI) / 180;

const NODES = [
  {
    id: 'engine',
    label: 'Engine\nnaas-abi-core',
    x: 0, y: 0,
    color: { background: '#1e293b', border: '#0f172a', highlight: { background: '#334155', border: '#0f172a' }, hover: { background: '#334155', border: '#0f172a' } },
    font: { color: '#ffffff' },
  },
  ...ports.map((p, i) => ({
    id: p.id,
    label: p.label,
    x: Math.round(R * Math.cos(toRad(p.angle))),
    y: Math.round(R * Math.sin(toRad(p.angle))),
    color: {
      background: PORT_COLORS[i].background,
      border: PORT_COLORS[i].border,
      highlight: { background: PORT_COLORS[i].background, border: PORT_COLORS[i].border },
      hover: { background: PORT_COLORS[i].background, border: PORT_COLORS[i].border },
    },
  })),
];

const EDGES = ports.map(p => ({
  from: 'engine',
  to: p.id,
  arrows: { to: { enabled: true, scaleFactor: 0.5 } },
  color: { color: '#cbd5e1', highlight: '#94a3b8', hover: '#94a3b8' },
  width: 2,
  smooth: { enabled: false },
}));

const OPTIONS = {
  layout: { randomSeed: 0 },
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false },
  edges: { smooth: { enabled: false } },
  nodes: { widthConstraint: { maximum: 200 } },
};

export default function ServicesDiagram() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;

      const nodes = new DataSet(NODES.map(n => ({
        ...n,
        shape: 'box',
        margin: { top: 9, bottom: 9, left: 12, right: 12 },
        font: { size: 12, face: 'ui-sans-serif, system-ui, sans-serif', ...(n.font || { color: '#1e293b' }) },
        borderWidth: 2,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 6, x: 0, y: 2 },
        widthConstraint: { minimum: 150, maximum: 210 },
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
        style={{ height: '660px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff', overflow: 'hidden' }}
      />
    </div>
  );
}
