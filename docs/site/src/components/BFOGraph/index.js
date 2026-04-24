import React, { useEffect, useRef } from 'react';

const C = (bg, bd) => ({ background: bg, border: bd, highlight: { background: bg, border: bd }, hover: { background: bg, border: bd } });

// Positions mirroring the BFO 7 Buckets diagram
// Top row: Occurrents (WHAT, WHEN)
// Bottom row: Continuants (WHO, WHERE, HOW-WE-KNOW, HOW-IT-IS, WHY)
const NODES = [
  {
    id: 'what',
    label: 'WHAT\nProcess',
    x: 30, y: -140,
    color: C('#bfdbfe', '#3b82f6'),
  },
  {
    id: 'when',
    label: 'WHEN\nTemporal Region',
    x: 380, y: -140,
    color: C('#bfdbfe', '#3b82f6'),
  },
  {
    id: 'who',
    label: 'WHO\nMaterial Entity',
    x: -360, y: 90,
    color: C('#dcfce7', '#22c55e'),
  },
  {
    id: 'where',
    label: 'WHERE\nSite',
    x: -130, y: 90,
    color: C('#fef3c7', '#f59e0b'),
  },
  {
    id: 'how-we-know',
    label: 'HOW-WE-KNOW\nInformation',
    x: 90, y: 90,
    color: C('#ede9fe', '#8b5cf6'),
  },
  {
    id: 'how-it-is',
    label: 'HOW-IT-IS\nQuality',
    x: 290, y: 90,
    color: C('#fce7f3', '#ec4899'),
  },
  {
    id: 'why',
    label: 'WHY\nRealizable Entity',
    x: 490, y: 90,
    color: C('#ccfbf1', '#14b8a6'),
  },
];

const ef = (color, size = 10) => ({ size, color: '#64748b', align: 'middle', strokeWidth: 2, strokeColor: '#ffffff' });

const EDGES = [
  { from: 'what', to: 'when',        label: 'occupies temporal region', color: { color: '#60a5fa' }, font: ef('#64748b') },
  { from: 'what', to: 'who',         label: 'has participant',           color: { color: '#60a5fa' }, font: ef('#64748b') },
  { from: 'what', to: 'where',       label: 'occurs in',                 color: { color: '#60a5fa' }, font: ef('#64748b') },
  { from: 'what', to: 'why',         label: 'realizes',                  color: { color: '#60a5fa' }, font: ef('#64748b') },
  { from: 'who',  to: 'where',       label: 'located in',                color: { color: '#86efac' }, font: ef('#64748b') },
  { from: 'who',  to: 'how-we-know', label: 'is carrier of',             color: { color: '#86efac' }, font: ef('#64748b') },
  { from: 'who',  to: 'why',         label: 'bearer of',                 color: { color: '#86efac' }, font: ef('#64748b') },
  { from: 'how-we-know', to: 'how-it-is', label: 'concretizes',         color: { color: '#c4b5fd' }, font: ef('#64748b') },
  { from: 'how-we-know', to: 'why',  label: 'concretizes',               color: { color: '#c4b5fd' }, font: ef('#64748b') },
];

// Band definitions for beforeDrawing (in canvas coords)
const BANDS = [
  { label: 'Occurrents',  color: 'rgba(219,234,254,0.35)', border: 'rgba(147,197,253,0.6)' },
  { label: 'Continuants', color: 'rgba(241,245,249,0.5)',  border: 'rgba(203,213,225,0.6)' },
];

// Approx node groups per band (used to compute bounding boxes)
const BAND_IDS = [
  ['what', 'when'],
  ['who', 'where', 'how-we-know', 'how-it-is', 'why'],
];

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

export default function BFOGraph() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;

      const nodes = new DataSet(NODES.map(n => ({
        ...n,
        shape: 'ellipse',
        margin: { top: 12, bottom: 12, left: 12, right: 12 },
        font: {
          size: 12,
          bold: true,
          color: '#1e293b',
          face: 'ui-sans-serif, system-ui, sans-serif',
          multi: true,
        },
        borderWidth: 2,
        shadow: { enabled: true, color: 'rgba(0,0,0,0.08)', size: 6, x: 0, y: 2 },
        widthConstraint: { minimum: 100, maximum: 140 },
      })));

      const edges = new DataSet(EDGES.map((e, i) => ({ id: i, ...e })));

      network = new Network(containerRef.current, { nodes, edges }, {
        physics: { enabled: false },
        interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false },
        edges: {
          arrows: { to: { enabled: true, scaleFactor: 0.45 } },
          width: 1.5,
          smooth: { enabled: true, type: 'cubicBezier', roundness: 0.3 },
        },
      });

      // Draw background bands for Occurrents and Continuants
      network.on('beforeDrawing', ctx => {
        const PAD = 55;
        const bandGroups = BAND_IDS.map(ids => {
          const positions = ids.map(id => network.getPosition(id));
          const xs = positions.map(p => p.x);
          const ys = positions.map(p => p.y);
          return {
            minX: Math.min(...xs) - PAD,
            maxX: Math.max(...xs) + PAD,
            minY: Math.min(...ys) - PAD,
            maxY: Math.max(...ys) + PAD,
          };
        });

        // Unified left/right to make bands span full width
        const allMinX = Math.min(...bandGroups.map(b => b.minX)) - 10;
        const allMaxX = Math.max(...bandGroups.map(b => b.maxX)) + 10;

        BANDS.forEach((band, i) => {
          const { minY, maxY } = bandGroups[i];
          const x = allMinX;
          const y = minY;
          const w = allMaxX - allMinX;
          const h = maxY - minY;

          ctx.save();
          roundRect(ctx, x, y, w, h, 12);
          ctx.fillStyle = band.color;
          ctx.fill();
          ctx.strokeStyle = band.border;
          ctx.lineWidth = 1.5;
          ctx.stroke();

          // Band label (top-left inside)
          ctx.font = 'bold 11px ui-sans-serif, system-ui, sans-serif';
          ctx.fillStyle = 'rgba(100,116,139,0.9)';
          ctx.fillText(band.label, x + 10, y + 16);
          ctx.restore();
        });
      });

      network.fit({ animation: false });
    })();
    return () => network?.destroy();
  }, []);

  return (
    <div style={{ margin: '24px 0' }}>
      <div
        ref={containerRef}
        style={{ height: '400px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#fafafa', overflow: 'hidden' }}
      />
    </div>
  );
}
