import React, { useEffect, useRef } from 'react';

const C = (bg, bd) => ({ background: bg, border: bd, highlight: { background: bg, border: bd }, hover: { background: bg, border: bd } });

const NODES = [
  // Column headers
  { id: 'h-data',    label: 'Any Data',    x: -370, y: -240, color: C('#eff6ff','#3b82f6'), header: true },
  { id: 'h-compute', label: 'Any Compute', x:    0, y: -240, color: C('#f0fdf4','#22c55e'), header: true },
  { id: 'h-model',   label: 'Any Model',   x:  370, y: -240, color: C('#faf5ff','#8b5cf6'), header: true },

  // Data stores (left column)
  { id: 'semantic',   label: 'Semantic data\nFuseki · RDF/SPARQL',   x: -370, y: -150, color: C('#dbeafe','#3b82f6') },
  { id: 'vector',     label: 'Vector data\nQdrant · embeddings',     x: -370, y:  -60, color: C('#dbeafe','#3b82f6') },
  { id: 'relational', label: 'Relational data\nPostgreSQL · SQL',    x: -370, y:   30, color: C('#dbeafe','#3b82f6') },
  { id: 'object',     label: 'Object data\nMinIO · S3-compatible',   x: -370, y:  120, color: C('#dbeafe','#3b82f6') },
  { id: 'ephemeral',  label: 'Ephemeral data\nRedis · key-value',    x: -370, y:  210, color: C('#dbeafe','#3b82f6') },

  // Compute modes (center column)
  { id: 'batch',       label: 'Batch\nDagster pipelines',        x: 0, y:  -90, color: C('#dcfce7','#22c55e') },
  { id: 'event',       label: 'Event-driven\nRabbitMQ message bus', x: 0, y:   30, color: C('#dcfce7','#22c55e') },
  { id: 'interactive', label: 'Interactive\nAgent tool calls',   x: 0, y:  150, color: C('#dcfce7','#22c55e') },

  // Model providers (right column)
  { id: 'openrouter', label: 'OpenRouter\n100+ cloud models',      x: 370, y:  -90, color: C('#ede9fe','#8b5cf6') },
  { id: 'ollama',     label: 'Ollama\nLocal · air-gapped',         x: 370, y:   30, color: C('#ede9fe','#8b5cf6') },
  { id: 'custom',     label: 'Custom endpoint\nOpenAI-compatible', x: 370, y:  150, color: C('#ede9fe','#8b5cf6') },
];

const EDGES = [
  { from: 'batch',       to: 'semantic',   color: { color: '#93c5fd', opacity: 0.7 }, dashes: true },
  { from: 'batch',       to: 'vector',     color: { color: '#93c5fd', opacity: 0.7 }, dashes: true },
  { from: 'event',       to: 'relational', color: { color: '#93c5fd', opacity: 0.7 }, dashes: true },
  { from: 'event',       to: 'object',     color: { color: '#93c5fd', opacity: 0.7 }, dashes: true },
  { from: 'interactive', to: 'openrouter', color: { color: '#c4b5fd', opacity: 0.7 }, dashes: true },
  { from: 'interactive', to: 'ollama',     color: { color: '#c4b5fd', opacity: 0.7 }, dashes: true },
];

const OPTIONS = {
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false },
  edges: {
    arrows: { to: { enabled: true, scaleFactor: 0.45 } },
    width: 1.5,
    smooth: { enabled: true, type: 'cubicBezier', roundness: 0.35 },
  },
};

export default function DataPlaneGraph() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;

      const nodes = new DataSet(NODES.map(n => ({
        ...n,
        shape: 'box',
        margin: { top: 9, bottom: 9, left: 13, right: 13 },
        font: {
          size: n.header ? 13 : 12,
          bold: n.header,
          color: '#1e293b',
          face: 'ui-sans-serif, system-ui, sans-serif',
          multi: true,
        },
        borderWidth: n.header ? 2 : 1.5,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.06)', size: 5, x: 0, y: 2 },
        widthConstraint: { minimum: 175, maximum: 195 },
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
        style={{ height: '520px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#fafafa', overflow: 'hidden' }}
      />
    </div>
  );
}
