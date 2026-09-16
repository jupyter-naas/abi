'use client';

import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, ArrowUpRight, Loader2 } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { useWorkspaceStore } from '@/stores/workspace';
import { useOntologyStore } from '@/stores/ontology';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { DASHBOARD_KINDS, buildOntologyDashboard, dashboardRoute, dashboardTerms, type DashboardFile } from '@/lib/ontology-dashboard';
import { dictionaryFiles } from '@/lib/ontology-file-filter';
import { dictionaryFilter, dictionaryFilterRoute, ontologyBrowser, termRoute } from '@/lib/ontology-navigation';
import { termKey } from '@/lib/ontology-context';
import { buildTermGraph } from '@/lib/ontology-term-graph';
import { inspectorTerm } from '@/lib/ontology-node-inspector';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { OntologyNodeInspector } from './ontology-node-inspector';
import { OntologyTopicIcon } from './ontology-topic-icon';
import { OntologyIconPicker } from './ontology-icon-picker';
import './ontology-dashboard.css';

type Inventory = { workspaceId: string; revision: number; files: DashboardFile[]; loading: boolean; error?: string };
type ApiFile = { path?: string; name?: string; module_name?: string; moduleName?: string; description?: string | null };
const EMPTY_TERMS: DictionaryTerm[] = [];
const PAGE_SIZE = 48;
const number = (value: number) => value.toLocaleString();
const tint = (color: string) => ({ '--tile-color': color } as CSSProperties);

export function OntologyDashboard() {
  const router = useRouter();
  const query = useSearchParams()?.toString() || '';
  const params = new URLSearchParams(query);
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const revision = useOntologyStore(state => state.graphRefreshTrigger);
  const dictionary = useOntologyDictionaryStore();
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [retry, setRetry] = useState(0);
  const [selection, setSelection] = useState<{ scope: string; root: string; node: string } | null>(null);
  const [page, setPage] = useState<{ scope: string; count: number } | null>(null);
  const kind = dictionaryFilter(query);
  const filePath = params.get('dashboardFile');
  const scope = `${workspaceId}:${query}:${revision}`;
  const workspaceTerms = dictionary.workspaceId === workspaceId ? dictionary.terms : EMPTY_TERMS;

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    setInventory({ workspaceId, revision, files: [], loading: true });
    void (async () => {
      try {
        const response = await authFetch(`${getApiUrl()}/api/ontology/ontologies?${new URLSearchParams({ workspace_id: workspaceId })}`);
        if (!response.ok) throw new Error('Could not load the workspace ontologies.');
        const data: { items?: ApiFile[] } = await response.json();
        if (!Array.isArray(data.items)) throw new Error('The ontology list could not be read.');
        const files = data.items.filter(item => typeof item?.path === 'string' && typeof item?.name === 'string')
          .map(item => ({ path: item.path!, name: item.name!, moduleName: item.module_name || item.moduleName || 'Other', description: item.description || undefined }));
        if (!cancelled) setInventory({ workspaceId, revision, files, loading: false });
      } catch (error) {
        if (!cancelled) setInventory({ workspaceId, revision, files: [], loading: false, error: error instanceof Error ? error.message : 'Could not load the workspace ontologies.' });
      }
    })();
    return () => { cancelled = true; };
  }, [workspaceId, revision, retry]);

  const currentInventory = inventory?.workspaceId === workspaceId && inventory.revision === revision ? inventory : null;
  const tiles = useMemo(() => buildOntologyDashboard(currentInventory?.files || [], workspaceTerms,
    dictionary.workspaceId === workspaceId ? dictionary.errors.map(error => error.path) : []),
  [currentInventory, workspaceTerms, dictionary.workspaceId, dictionary.errors, workspaceId]);
  const fileFilters = ontologyBrowser(query) === 'files' && params.get('ontology') ? [params.get('ontology')!] : dictionaryFiles(query);
  const scopedTiles = tiles.filter(tile => !fileFilters.length || fileFilters.includes(tile.path));
  const selectedFile = filePath ? scopedTiles.find(tile => tile.path === filePath) : undefined;
  const activeTiles = filePath ? selectedFile ? [selectedFile] : [] : scopedTiles;
  const terms = dashboardTerms(activeTiles);
  const filteredTerms = terms.filter(term => kind === 'all' || term.type === kind);
  const definedCount = terms.filter(term => term.description?.trim() || term.definitions?.some(definition => definition.value.trim())).length;
  const missingDefinitionCount = terms.length - definedCount;
  const definitionCoverage = terms.length ? (definedCount / terms.length).toLocaleString(undefined, { style: 'percent', maximumFractionDigits: 1 }) : '—';
  const groups = new Map<string, typeof tiles>();
  for (const tile of activeTiles) {
    if (kind !== 'all' && !tile.failed && !tile.terms.some(term => term.type === kind)) continue;
    const group = groups.get(tile.moduleName) || [];
    group.push(tile); groups.set(tile.moduleName, group);
  }
  const visibleLimit = page?.scope === scope ? page.count : PAGE_SIZE;
  const visibleTerms = filteredTerms.slice(0, visibleLimit);
  const root = selection?.scope === scope ? terms.find(term => termKey(term) === selection.root) : undefined;
  const graph = useMemo(() => root ? buildTermGraph(root, workspaceTerms) : null, [root, workspaceTerms]);
  const node = graph?.nodes.find(item => item.id === selection?.node);
  const inspectedTerm = node ? inspectorTerm(node, workspaceTerms) : undefined;
  const navigate = (next: URLSearchParams) => router.push(`?${next}`, { scroll: false });
  const openTerm = (term: DictionaryTerm, network = false) => {
    const next = termRoute(query, term);
    next.delete('dashboardFile');
    if (network) next.set('view', 'network');
    navigate(next);
  };
  const filterKind = (type: DictionaryTerm['type']) => {
    const next = dictionaryFilterRoute(query, kind === type ? 'all' : type);
    next.set('view', 'overview');
    navigate(next);
  };
  const reload = () => { setRetry(value => value + 1); if (workspaceId) void dictionary.load(workspaceId, revision, true); };

  if (!currentInventory || currentInventory.loading || dictionary.loading || dictionary.workspaceId !== workspaceId) {
    return <div className="ontology-dashboard-state" role="status"><Loader2 size={16} className="animate-spin" />Loading ontology dashboard…</div>;
  }
  if (currentInventory.error || dictionary.error) {
    return <div className="ontology-dashboard-state" role="alert"><p>{currentInventory.error || dictionary.error}</p><button type="button" onClick={reload}>Try again</button></div>;
  }
  return <div className="ontology-dashboard">
    <main className="ontology-dashboard-main" aria-label="Ontology dashboard">
      <header className="ontology-dashboard-header">
        {filePath && <button type="button" className="ontology-dashboard-back" onClick={() => navigate(dashboardRoute(query))}><ArrowLeft size={14} />All ontologies in scope</button>}
        {selectedFile && <OntologyIconPicker subject={selectedFile} className="ontology-dashboard-title-icon" />}
        <div className="ontology-dashboard-heading"><h1>{filePath ? selectedFile?.name || 'Ontology unavailable' : 'Ontology dashboard'}</h1>
          <span>{filePath ? selectedFile?.moduleName : fileFilters.length ? `${scopedTiles.length} selected ontologies` : `${tiles.length} workspace ontologies`}</span></div>
        <p>{filePath ? selectedFile?.description || 'Select a term to inspect its definition and connections.' : 'A table of the workspace vocabulary. Select an ontology to explore its terms.'}</p>
      </header>
      {dictionary.errors.length > 0 && <p className="ontology-dashboard-notice" role="status">{dictionary.errors.length} ontology {dictionary.errors.length === 1 ? 'file could' : 'files could'} not be read. Counts reflect the loaded data. <button type="button" onClick={reload}>Retry</button></p>}
      <div className="ontology-dashboard-summary">
        <div><strong>{number(terms.length)}</strong><span>unique terms</span></div>
        <div><strong>{definitionCoverage}</strong><span>{number(definedCount)} defined</span></div>
        <div><strong>{number(missingDefinitionCount)}</strong><span>still to define</span></div>
        <p>Shared terms are counted once. {selectedFile && <span title={selectedFile.path}>{selectedFile.path.split('/').pop()}</span>}</p>
      </div>
      <div className="ontology-dashboard-metrics" aria-label="Term types">
        {DASHBOARD_KINDS.map(item => <button type="button" key={item.type} style={tint(item.color)} aria-pressed={kind === item.type} onClick={() => filterKind(item.type)}>
          <span>{item.label}</span><strong>{number(terms.filter(term => term.type === item.type).length)}</strong><span className="ontology-dashboard-metric-symbol" aria-hidden="true">{item.symbol}</span>
        </button>)}
      </div>
      <div className="ontology-dashboard-table-heading"><h2>{filePath ? 'Terms' : 'Ontologies'}</h2><span>{kind === 'all' ? filePath ? `${filteredTerms.length} terms` : 'Grouped by module' : `${DASHBOARD_KINDS.find(item => item.type === kind)?.label} · select the active count to show all`}</span></div>
      {filePath ? !selectedFile ? <p className="ontology-dashboard-empty">This ontology is not available in the current workspace or file selection.</p>
        : selectedFile.failed ? <p className="ontology-dashboard-empty">This ontology could not be read. <button type="button" onClick={reload}>Try again</button></p>
        : !filteredTerms.length ? <p className="ontology-dashboard-empty">{terms.length ? 'No terms match the selected type.' : 'No terms are declared in this ontology.'}</p>
        : <>
          <div className="ontology-dashboard-grid" aria-label="Terms">
            {visibleTerms.map((term, index) => {
              const family = DASHBOARD_KINDS.find(item => item.type === term.type)!;
              return <button type="button" key={termKey(term)} className="ontology-dashboard-tile" style={tint(family.color)}
                aria-pressed={selection?.scope === scope && selection.root === termKey(term)} title={`${term.name}\n${term.description || term.id}`} onClick={() => setSelection({ scope, root: termKey(term), node: termKey(term) })}>
                <span className="ontology-dashboard-tile-index">{String(index + 1).padStart(2, '0')}<span>{family.symbol}</span></span>
                <OntologyTopicIcon subject={term} className="ontology-dashboard-tile-icon" />
                <strong>{term.name}</strong><span className="ontology-dashboard-tile-meta">{family.label}<ArrowUpRight size={12} /></span>
              </button>;
            })}
          </div>
          {filteredTerms.length > visibleLimit && <button type="button" className="ontology-dashboard-more" onClick={() => setPage({ scope, count: visibleLimit + PAGE_SIZE })}>Show more terms ({visibleLimit} of {filteredTerms.length})</button>}
        </>
        : groups.size ? [...groups].map(([moduleName, files]) => <section className="ontology-dashboard-group" key={moduleName} aria-label={moduleName}>
          <h3>{moduleName}<span>{files.length}</span></h3><div className="ontology-dashboard-grid">
            {files.map(tile => {
              const dominant = [...DASHBOARD_KINDS].sort((a, b) => tile.terms.filter(term => term.type === b.type).length - tile.terms.filter(term => term.type === a.type).length)[0];
              const count = kind === 'all' ? tile.terms.length : tile.terms.filter(term => term.type === kind).length;
              return <button type="button" key={tile.path} className="ontology-dashboard-tile" style={tint(dominant.color)} data-failed={tile.failed || undefined}
                title={`${tile.name}\n${tile.path.split('/').pop()}`} onClick={() => navigate(dashboardRoute(query, tile.path))}>
                <span className="ontology-dashboard-tile-index">{String(tile.index).padStart(2, '0')}<ArrowUpRight size={12} /></span>
                <OntologyTopicIcon subject={tile} className="ontology-dashboard-tile-icon" />
                <strong>{tile.name}</strong><span className="ontology-dashboard-tile-meta">{tile.failed ? 'Could not load' : `${number(count)} ${kind === 'all' ? 'terms' : DASHBOARD_KINDS.find(item => item.type === kind)?.label.toLowerCase()}`}</span>
              </button>;
            })}
          </div>
        </section>) : <p className="ontology-dashboard-empty">{tiles.length ? 'No ontologies match the current filters.' : 'No ontology files are available in this workspace.'}</p>}
      <p className="ontology-dashboard-footnote">{filePath ? 'Colors indicate term type.' : 'One tile per ontology file. Colors indicate its most common term type.'}</p>
    </main>
    {node && graph && <OntologyNodeInspector node={node} nodes={graph.nodes} edges={graph.edges} terms={workspaceTerms}
      onClose={() => setSelection(null)} onSelect={id => setSelection(current => current ? { ...current, node: id } : null)}
      onOpenFullPage={term => openTerm(term)} onExplore={inspectedTerm ? () => openTerm(inspectedTerm, true) : undefined} exploreLabel="Explore network" />}
  </div>;
}
