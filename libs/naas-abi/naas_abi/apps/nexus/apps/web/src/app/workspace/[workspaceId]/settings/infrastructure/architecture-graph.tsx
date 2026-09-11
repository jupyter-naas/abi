'use client';
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { architecture } from './architecture-model';
import { describeDependency, graphPositions, graphRoute, GRAPH_COLUMN, DIAGRAM_LAYERS } from './graph-model';
import { LinkTooltip, type LinkHover } from './link-tooltip';
import { useInfrastructure } from './infrastructure-store';

export default function ArchitectureGraph() {
  const { componentId, layerId, command, select } = useInfrastructure();
  const nodes = useMemo(graphPositions, []);
  const positions = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes]);
  const root = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const markerId = useId().replaceAll(':', '');
  const bounds = useMemo(() => {
    const x = Math.min(...nodes.map(n => n.x)) - 150, y = Math.min(...nodes.map(n => n.y)) - 110;
    return { x, y, w: Math.max(...nodes.map(n => n.x)) - x + 150, h: Math.max(...nodes.map(n => n.y)) - y + 50 };
  }, [nodes]);
  const [view, setView] = useState(bounds);
  const [hover, setHover] = useState<LinkHover>(null);
  const down = useRef<{ x: number; y: number; view: typeof bounds; moved: boolean } | null>(null);
  const previous = useRef(command.sequence);
  const connected = new Set([componentId]);
  architecture.edges.forEach(e => { if (e.source === componentId || e.target === componentId) { connected.add(e.source); connected.add(e.target); } });
  useEffect(() => {
    if (previous.current === command.sequence) return;
    previous.current = command.sequence; setHover(null);
    if (command.type !== 'focus') {
      const factor = command.type === 'in' ? 0.8 : 1.25;
      setView(v => { const w = Math.max(bounds.w * 0.12, Math.min(bounds.w * 3, v.w * factor)); const ratio = w / v.w; return { x: v.x + (v.w - w) / 2, y: v.y + v.h * (1 - ratio) / 2, w, h: v.h * ratio }; });
    } else setView(bounds);
  }, [command, bounds]);
  useEffect(() => {
    const element = root.current!;
    function wheel(e: WheelEvent) {
      e.preventDefault(); setHover(null);
      const rect = element.getBoundingClientRect(); const px = (e.clientX - rect.left) / rect.width, py = (e.clientY - rect.top) / rect.height;
      setView(v => { const w = Math.max(bounds.w * 0.12, Math.min(bounds.w * 3, v.w * Math.exp(e.deltaY * 0.001))); const ratio = w / v.w; return { x: v.x + v.w * px * (1 - ratio), y: v.y + v.h * py * (1 - ratio), w, h: v.h * ratio }; });
    }
    element.addEventListener('wheel', wheel, { passive: false });
    return () => element.removeEventListener('wheel', wheel);
  }, [bounds]);
  return <div className="infrastructure-graph" ref={root}>
    <svg ref={svg} viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} aria-label="ABI architecture diagram" onPointerDown={e => { if (e.button !== 0) return; down.current = { x: e.clientX, y: e.clientY, view, moved: false }; }} onPointerMove={e => {
      const d = down.current; if (!d || !e.buttons) return;
      if (Math.hypot(e.clientX - d.x, e.clientY - d.y) < 4 && !d.moved) return;
      d.moved = true; e.currentTarget.setPointerCapture(e.pointerId); setHover(null);
      const scale = svg.current!.getScreenCTM()!.a;
      setView({ ...d.view, x: d.view.x - (e.clientX - d.x) / scale, y: d.view.y - (e.clientY - d.y) / scale });
    }} onPointerUp={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); }} onPointerCancel={() => { down.current = null; }} onPointerLeave={() => { setHover(null); }}>
      <defs><marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>
      {DIAGRAM_LAYERS.map((layer, i) => <g key={layer.id} className="infrastructure-graph-lane">
        <rect x={i * GRAPH_COLUMN - 122} y={-88} width={244} height={Math.max(...nodes.map(n => n.y)) + 124} rx={6} />
        <path d={`M ${i * GRAPH_COLUMN - 110} -72 h 220`} style={{ stroke: layer.color }} />
        <text x={i * GRAPH_COLUMN - 110} y={-48}>{layer.label}</text>
        <text className="infrastructure-graph-lane-count" x={i * GRAPH_COLUMN - 110} y={-30}>{architecture.components.filter(c => c.layer === layer.id).length} components</text>
      </g>)}
      {architecture.edges.map(edge => {
        const a = positions.get(edge.source)!, b = positions.get(edge.target)!;
        const relevant = componentId ? edge.source === componentId || edge.target === componentId
          : layerId ? architecture.components.some(c => (c.id === edge.source || c.id === edge.target) && c.layer === layerId) : true;
        if (!relevant) return null;
        const route = graphRoute(a, b);
        const path = route.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');
        const show = (x: number, y: number) => { const r = root.current!.getBoundingClientRect(); setHover({ edge, x: Math.max(8, Math.min(x - r.left + 12, r.width - 300)), y: Math.max(8, Math.min(y - r.top + 12, r.height - 100)) }); };
        return <g key={`${edge.source}:${edge.target}`} className={`infrastructure-graph-edge ${componentId || layerId ? 'is-focused' : 'is-relevant'}`}>
          <path d={path} markerEnd={`url(#${markerId})`} />
          <path d={path} className="infrastructure-graph-edge-hit" tabIndex={0} aria-label={`${describeDependency(edge).title}. ${describeDependency(edge).detail}`} onPointerMove={e => { if (!e.buttons) show(e.clientX, e.clientY); }} onPointerLeave={() => setHover(null)} onFocus={e => { const r = e.currentTarget.getBoundingClientRect(); show(r.x + r.width / 2, r.y + r.height / 2); }} onBlur={() => setHover(null)} />
        </g>;
      })}
      {architecture.components.map(c => {
        const p = positions.get(c.id)!; const layer = architecture.layers.find(l => l.id === c.layer)!;
        const active = componentId ? connected.has(c.id) : !layerId || layerId === c.layer;
        return <g key={c.id} transform={`translate(${p.x},${p.y})`} className={`infrastructure-graph-node ${active ? 'is-relevant' : ''} ${componentId === c.id ? 'is-selected' : ''}`} role="button" tabIndex={0} aria-label={`${c.label}, ${layer.label}, ${c.files} files`} onClick={() => { if (!down.current?.moved) select(c.layer, c.id); down.current = null; }} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(c.layer, c.id); } }}>
          <title>{c.label} · {layer.label}</title><rect x="-110" y="-24" width="220" height="48" rx="4" /><rect x="-110" y="-24" width="4" height="48" style={{ fill: layer.color, stroke: 'none' }} /><text x="-96" y="-2">{c.label.length > 27 ? `${c.label.slice(0, 26)}…` : c.label}</text><text className="infrastructure-graph-node-detail" x="-96" y="13">{c.files} files</text>
        </g>;
      })}
    </svg><LinkTooltip hover={hover} />
  </div>;
}
