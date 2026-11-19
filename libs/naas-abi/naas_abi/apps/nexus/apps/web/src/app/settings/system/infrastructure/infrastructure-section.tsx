'use client';
import { useMemo, type CSSProperties } from 'react';
import { ArrowDownLeft, ArrowUpRight, Layers, Search } from 'lucide-react';
import { architecture } from './architecture-model';
import { useInfrastructure } from './infrastructure-store';
import './infrastructure.css';
const number = (n: number) => n.toLocaleString('en-US');
export function InfrastructureSection() {
  const { layerId, componentId, search, tab, select, reset, setSearch, setTab, setComponentId } = useInfrastructure();
  const layer = architecture.layers.find(l => l.id === layerId);
  const component = architecture.components.find(c => c.id === componentId);
  const componentMap = useMemo(() => new Map(architecture.components.map(c => [c.id, c])), []);
  const filtered = architecture.components.filter(c => (!layerId || c.layer === layerId) && `${c.label} ${c.id}`.toLowerCase().includes(search.toLowerCase()));
  const selectedComponents = component ? [component] : architecture.components.filter(c => !layerId || c.layer === layerId);
  const sum = (key: 'files' | 'lines' | 'classes' | 'functions' | 'tests') => selectedComponents.reduce((n, c) => n + c[key], 0);
  const outbound = architecture.edges.filter(e => e.source === componentId);
  const inbound = architecture.edges.filter(e => e.target === componentId);
  return <div className="infrastructure-sidebar">
    <div className="infrastructure-sidebar-tabs"><button aria-pressed={tab === 'layers'} onClick={() => setTab('layers')}>Architecture</button><button aria-pressed={tab === 'inspector'} onClick={() => setTab('inspector')}>Inspector</button></div>
    {tab === 'layers' ? <>
      <button className={`infrastructure-tree-row ${!layerId ? 'is-active' : ''}`} onClick={reset}><Layers size={14} /><span>Entire system</span><small>{architecture.components.length}</small></button>
      {architecture.layers.map((item) => <button key={item.id} className={`infrastructure-tree-row ${layerId === item.id ? 'is-active' : ''}`} aria-pressed={layerId === item.id} onClick={() => select(item.id)}><span className="infrastructure-layer-dot" style={{ '--layer-color': item.color } as CSSProperties} /><span>{item.label}</span><small>{architecture.components.filter(c => c.layer === item.id).length}</small></button>)}
      <label className="infrastructure-search"><Search size={14} /><input aria-label="Search components" placeholder="Find a component…" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <div className="infrastructure-component-list">{filtered.map(c => <button key={c.id} onClick={() => select(c.layer, c.id)}><span><strong>{c.label}</strong><small>{c.files} files</small></span><ArrowUpRight size={13} /></button>)}{!filtered.length && <p>No matching components.</p>}</div>
    </> : <div className="infrastructure-inspector">        <div className="infrastructure-inspector-title" aria-live="polite"><div className="infrastructure-eyebrow">{component ? 'COMPONENT' : layer ? 'LAYER OVERVIEW' : 'SYSTEM OVERVIEW'}</div><h2>{component?.label ?? layer?.label ?? 'ABI architecture'}</h2><p>{component ? component.id : layer?.description ?? 'Five logical layers, from applications to infrastructure adapters. Select a layer to bring its plane into focus.'}</p></div>
        <div className="infrastructure-metrics">{([['Source files', sum('files')], ['Lines of code', sum('lines')], ['Classes', sum('classes')], ['Functions', sum('functions')], ['Test files', sum('tests')], ['Components', selectedComponents.length]] as const).map(([label, value]) => <div key={label}><span>{label}</span><strong>{number(value)}</strong></div>)}</div>
        <p className="infrastructure-metric-note">Python only · lines include comments and blanks · test files are counted, not executed.</p>
        {component ? <>
          <button className="infrastructure-back" onClick={() => setComponentId(null)}>← All components in this layer</button>
          <div className="infrastructure-dependencies"><h3><ArrowUpRight size={14} /> Depends on <span>{outbound.length}</span></h3>{outbound.length ? outbound.map(edge => <button key={edge.target} onClick={() => select(componentMap.get(edge.target)!.layer, edge.target)}><span>{componentMap.get(edge.target)!.label}<small>{Object.entries(edge.relations).map(([relation, count]) => `${relation.replaceAll('_', ' ')}: ${count}`).join(' · ')}</small></span><ArrowUpRight size={14} /></button>) : <p>No cross-component dependencies resolved.</p>}
          <h3><ArrowDownLeft size={14} /> Used by <span>{inbound.length}</span></h3>{inbound.length ? inbound.map(edge => <button key={edge.source} onClick={() => select(componentMap.get(edge.source)!.layer, edge.source)}><span>{componentMap.get(edge.source)!.label}<small>{edge.count} extracted relationships</small></span><ArrowUpRight size={14} /></button>) : <p>No incoming dependencies resolved.</p>}</div>
          <details className="infrastructure-files"><summary>Source files ({component.sourcePaths.length})</summary>{component.sourcePaths.map(path => <code key={path}>{path}</code>)}</details>
        </> : <>
          <label className="infrastructure-search"><Search size={15} /><input aria-label="Search components" placeholder="Find a component…" value={search} onChange={e => setSearch(e.target.value)} /></label>
          <div className="infrastructure-component-list">{filtered.map(c => <button key={c.id} onClick={() => select(c.layer, c.id)}><span><strong>{c.label}</strong><small>{c.files} files · {c.functions} functions</small></span><ArrowUpRight size={14} /></button>)}{!filtered.length && <p>No components match “{search}”.</p>}</div>
        </>}</div>}
    <details className="infrastructure-about"><summary>About this map</summary><p>{architecture.extractor} · {architecture.revision}</p><p>{architecture.scope}</p><p>{architecture.edges.length} resolved component dependencies. Dynamic wiring may be absent.</p></details>
  </div>;
}
