'use client';
import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { Focus, Minus, Plus, RotateCcw } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { architecture } from './architecture-model';
import { useInfrastructure } from './infrastructure-store';
import { InfrastructureMenu } from './infrastructure-menu';
import { InfrastructureSection } from './infrastructure-section';
import './infrastructure.css';
const ArchitectureScene = dynamic(() => import('./architecture-scene'), { ssr: false, loading: () => <div className="infrastructure-scene-error">Loading architecture…</div> });
const ArchitectureGraph = dynamic(() => import('./architecture-graph'), { ssr: false });
export default function Infrastructure() {
  const { viewMode, setViewMode, layerId, componentId, expanded, dependencies, command, select, reset, move } = useInfrastructure();
  const menu = useMemo(() => <InfrastructureMenu />, []);
  const layer = architecture.layers.find(l => l.id === layerId);
  return <section className="infrastructure-page" aria-label="ABI infrastructure">
    <Header title="Infrastructure" nav={menu} />
    <div className="infrastructure-mobile-nav"><InfrastructureMenu /><details><summary>Architecture & inspector</summary><InfrastructureSection /></details></div>
    <div className="infrastructure-viewport">
      <div className="infrastructure-view-heading"><div className="infrastructure-view-selector" aria-label="Visualization"><button aria-pressed={viewMode === 'layers'} onClick={() => setViewMode('layers')}>Layers</button><button aria-pressed={viewMode === 'graph'} onClick={() => setViewMode('graph')}>Diagram</button></div><button onClick={reset}>ABI</button><span>/</span><span>{layer?.label ?? 'Entire system'}</span>{layer && <button className="infrastructure-exit" onClick={reset}>Exit focus</button>}</div>
      <div className="infrastructure-canvas-area">{viewMode === 'graph' ? <ArchitectureGraph /> : <ArchitectureScene layer={layerId} component={componentId} expanded={expanded} dependencies={dependencies} command={command} onSelect={select} />}</div>
      <div className="infrastructure-view-tools"><button onClick={() => move()} title="Fit view" aria-label="Fit view"><Focus size={16} /></button><button onClick={() => move('in')} title="Zoom in" aria-label="Zoom in"><Plus size={16} /></button><button onClick={() => move('out')} title="Zoom out" aria-label="Zoom out"><Minus size={16} /></button><button onClick={reset} title="Reset view" aria-label="Reset view"><RotateCcw size={16} /></button></div>
      <footer className="infrastructure-view-footer"><span>{viewMode === 'graph' ? 'Drag to pan · Scroll to zoom · Hover links for details' : 'Drag to orbit · Scroll to zoom · Hover links for details'}</span><span>Source snapshot · {architecture.components.length} components{dependencies || viewMode === 'graph' ? ' · Dependencies shown' : ''}</span></footer>
    </div>
  </section>;
}
