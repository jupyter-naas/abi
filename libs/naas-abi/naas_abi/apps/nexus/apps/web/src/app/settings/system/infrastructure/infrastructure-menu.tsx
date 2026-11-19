'use client';
import { useEffect, useRef } from 'react';
import { architecture } from './architecture-model';
import { useInfrastructure } from './infrastructure-store';
import type { InfrastructureView } from './infrastructure';
import './infrastructure.css';

export function InfrastructureMenu({ view }: { view: InfrastructureView }) {
  const { expanded, dependencies, reset, move, toggleExpanded, toggleDependencies } = useInfrastructure();
  const diagrams = view === 'diagrams';
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: Event) => {
      if ((e instanceof KeyboardEvent && e.key === 'Escape') || (e.type === 'pointerdown' && !root.current?.contains(e.target as Node))) root.current?.querySelectorAll('details').forEach(d => { d.open = false; });
    };
    document.addEventListener('pointerdown', close); document.addEventListener('keydown', close);
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', close); };
  }, []);
  function run(action: () => void) { action(); root.current?.querySelectorAll('details').forEach(d => { d.open = false; }); }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(architecture, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'abi-architecture.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="infrastructure-menu" ref={root}>
    <details onToggle={e => { if (e.currentTarget.open) root.current?.querySelectorAll('details').forEach(d => { if (d !== e.currentTarget) d.open = false; }); }}><summary>File</summary><div className="infrastructure-menu-popup"><button onClick={() => run(download)}>Export architecture…</button></div></details>
    <details onToggle={e => { if (e.currentTarget.open) root.current?.querySelectorAll('details').forEach(d => { if (d !== e.currentTarget) d.open = false; }); }}><summary>View</summary><div className="infrastructure-menu-popup">
      <button onClick={() => run(reset)}>Entire system</button><button onClick={() => run(() => move())}>Fit view</button><button onClick={() => run(() => move('in'))}>Zoom in</button><button onClick={() => run(() => move('out'))}>Zoom out</button><hr />
      <button disabled={diagrams} aria-pressed={expanded} onClick={() => run(toggleExpanded)}>Decompose <span>{expanded ? '✓' : ''}</span></button><button disabled={diagrams} aria-pressed={dependencies || diagrams} onClick={() => run(toggleDependencies)}>Dependencies <span>{dependencies ? '✓' : ''}</span></button>
    </div></details>
  </div>;
}
