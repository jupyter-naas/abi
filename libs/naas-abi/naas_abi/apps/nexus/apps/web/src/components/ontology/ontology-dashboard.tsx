'use client';

import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, ArrowUpRight, Loader2 } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { useWorkspaceStore } from '@/stores/workspace';
import { useOntologyStore } from '@/stores/ontology';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { DASHBOARD_KINDS, buildOntologyDashboard, dashboardRoute, dashboardTerms, dashboardCoverage, dashboardOntologies, dashboardKindRoute, type DashboardFile } from '@/lib/ontology-dashboard';
import { systemOntologyPaths } from '@/lib/ontology-system-filter';
import { dictionaryFiles } from '@/lib/ontology-file-filter';
import { dictionaryFilters, ontologyBrowser, termRoute } from '@/lib/ontology-navigation';
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
  const kinds = dictionaryFilters(query);
  const kind = params.get('dashboardType') === 'ontology' ? 'ontology' : !kinds.length ? 'all' : kinds.length === 1 ? kinds[0] : 'multiple';
  const kindLabel = kind === 'multiple' ? `${kinds.length} types selected` : DASHBOARD_KINDS.find(item => item.type === kind)?.label;
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
  const systemPaths = useMemo(() => systemOntologyPaths(workspaceTerms, query), [workspaceTerms, query]);
  const scopedTiles = tiles.filter(tile => (systemPaths === null || systemPaths.has(tile.path)) && (!fileFilters.length || fileFilters.includes(tile.path)));
  const selectedFile = filePath ? scopedTiles.find(tile => tile.path === filePath) : undefined;
  const activeTiles = filePath ? selectedFile ? [selectedFile] : [] : scopedTiles;
  const terms = dashboardTerms(activeTiles);
  const activePaths = activeTiles.map(tile => tile.path);
  const ontologies = dashboardOntologies(dictionary.ontologies || [], activePaths);
  const coverage = dashboardCoverage([...terms, ...ontologies], activePaths);
  const filteredTerms = terms.filter(term => !kinds.length || kinds.includes(term.type));
  const groups = new Map<string, typeof tiles>();
  for (const tile of activeTiles) {
    if (kind !== 'all' && !tile.failed && !(kind === 'ontology'
      ? ontologies.some(item => item.sources?.some(source => source.path === tile.path))
      : tile.terms.some(term => kinds.includes(term.type)))) continue;
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
          <span>{filePath ? selectedFile?.moduleName : fileFilters.length || systemPaths !== null ? `${scopedTiles.length} selected ontologies` : `${tiles.length} workspace ontologies`}</span></div>
        <p>{filePath ? selectedFile?.description || 'Select a type to inspect its definition and connections.' : 'A table of the workspace vocabulary. Select an ontology to explore its types.'}</p>
      </header>
      {dictionary.errors.length > 0 && <p className="ontology-dashboard-notice" role="status">{dictionary.errors.length} ontology {dictionary.errors.length === 1 ? 'file could' : 'files could'} not be read. Counts reflect the loaded data. <button type="button" onClick={reload}>Retry</button></p>}
      <div className="ontology-dashboard-table-heading"><h2>Overview</h2></div>
      <div className="ontology-dashboard-metrics ontology-dashboard-summary">
        <div className="ontology-dashboard-metric" title="Number of RDF Types declared in the selected ontologies. Each IRI and category is counted once across files, including ontology declarations and named individuals."><span>Unique Types</span><strong>{number(coverage.total)}</strong>
          <span className="ontology-dashboard-metric-note">Shared types are counted once per IRI and category. {selectedFile && <span title={selectedFile.path}>{selectedFile.path.split('/').pop()}</span>}</span>
        </div>
        {coverage.metrics.map(metric => <div key={metric.key} className="ontology-dashboard-metric" title={`Percentage of RDF Types with a non-empty ${metric.predicate} literal in the selected ontologies.`}>
          <span>{metric.label}</span>
          <strong>{metric.ratio === null ? '—' : metric.ratio.toLocaleString(undefined, { style: 'percent', maximumFractionDigits: 1 })}</strong>
          <span className="ontology-dashboard-metric-note">{number(metric.present)} with · {number(metric.missing)} missing</span>
        </div>)}
      </div>
      <div className="ontology-dashboard-table-heading"><h2>Breakdown by types</h2></div>
      <div className="ontology-dashboard-metrics" aria-label="RDF Types">
        {DASHBOARD_KINDS.map(item => <button type="button" key={item.type} className="ontology-dashboard-metric" style={tint(item.color)} aria-pressed={item.type === 'ontology' ? kind === 'ontology' : kind !== 'ontology' && kinds.includes(item.type)} onClick={() => navigate(dashboardKindRoute(query, item.type))} title={item.type === 'ontology' ? 'Distinct owl:Ontology declarations in the selected files.' : undefined}>
          <span>{item.label}</span><strong>{number(item.type === 'ontology' ? ontologies.length : terms.filter(term => term.type === item.type).length)}</strong><span className="ontology-dashboard-metric-symbol" aria-hidden="true">{item.symbol}</span>
        </button>)}
      </div>
      <div className="ontology-dashboard-table-heading"><h2>{filePath && kind !== 'ontology' ? 'Types' : 'Ontologies'}</h2><span>{kind === 'all' ? filePath ? `${filteredTerms.length} types` : 'Grouped by module' : kind === 'multiple' ? `${kindLabel} · adjust in All types` : `${kindLabel} · select the active count to show all`}</span></div>
      {filePath && kind !== 'ontology' ? !selectedFile ? <p className="ontology-dashboard-empty">This ontology is not available in the current workspace or file selection.</p>
        : selectedFile.failed ? <p className="ontology-dashboard-empty">This ontology could not be read. <button type="button" onClick={reload}>Try again</button></p>
        : !filteredTerms.length ? <p className="ontology-dashboard-empty">{terms.length ? 'No types match the selected category.' : 'No types are declared in this ontology.'}</p>
        : <>
          <div className="ontology-dashboard-grid" aria-label="Types">
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
          {filteredTerms.length > visibleLimit && <button type="button" className="ontology-dashboard-more" onClick={() => setPage({ scope, count: visibleLimit + PAGE_SIZE })}>Show more types ({visibleLimit} of {filteredTerms.length})</button>}
        </>
        : groups.size ? [...groups].map(([moduleName, files]) => <section className="ontology-dashboard-group" key={moduleName} aria-label={moduleName}>
          <h3>{moduleName}<span>{files.length}</span></h3><div className="ontology-dashboard-grid">
            {files.map(tile => {
              const dominant = [...DASHBOARD_KINDS].filter(item => item.type !== 'ontology').sort((a, b) => tile.terms.filter(term => term.type === b.type).length - tile.terms.filter(term => term.type === a.type).length)[0];
              const count = kind === 'ontology' ? dashboardOntologies(ontologies, [tile.path]).length : kind === 'all' ? tile.terms.length : tile.terms.filter(term => kinds.includes(term.type)).length;
              return <button type="button" key={tile.path} className="ontology-dashboard-tile" style={tint(dominant.color)} data-failed={tile.failed || undefined}
                title={`${tile.name}\n${tile.path.split('/').pop()}`} onClick={() => navigate(dashboardRoute(query, tile.path))}>
                <span className="ontology-dashboard-tile-index">{String(tile.index).padStart(2, '0')}<ArrowUpRight size={12} /></span>
                <OntologyTopicIcon subject={tile} className="ontology-dashboard-tile-icon" />
                <strong>{tile.name}</strong><span className="ontology-dashboard-tile-meta">{tile.failed ? 'Could not load' : `${number(count)} ${kind === 'all' || kind === 'multiple' ? 'types' : kindLabel?.toLowerCase()}`}</span>
              </button>;
            })}
          </div>
        </section>) : <p className="ontology-dashboard-empty">{tiles.length ? 'No ontologies match the current filters.' : 'No ontology files are available in this workspace.'}</p>}
      <p className="ontology-dashboard-footnote">{filePath && kind !== 'ontology' ? 'Colors indicate type category.' : 'One tile per ontology file. Colors indicate its most common type category.'}</p>
    </main>
    {node && graph && <OntologyNodeInspector node={node} nodes={graph.nodes} edges={graph.edges} terms={workspaceTerms}
      onClose={() => setSelection(null)} onSelect={id => setSelection(current => current ? { ...current, node: id } : null)}
      onOpenFullPage={term => openTerm(term)} onExplore={inspectedTerm ? () => openTerm(inspectedTerm, true) : undefined} exploreLabel="Explore network" />}
  </div>;
}
