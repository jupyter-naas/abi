'use client';

import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Search } from 'lucide-react';
import { GraphHeader } from '../graph-header';
import { IndividualsTable, type ApiDiscoveryInstance } from '../individuals-table';
import { InstanceInspector } from '../instance-inspector';
import { preloadExplorerNetwork, ExplorerNetwork, type ExplorerNetworkData } from './explorer-network';
import { ExplorerClassDetails } from './explorer-class-details';
import { useGraphRequest } from '@/hooks/use-graph-request';
import { useGraphExplorer } from '@/stores/graph-explorer';
import { explorerQuery, explorerScope, pendingPollDelay, type ExplorerKpis, type ExplorerView, type ExplorerOverview } from '@/lib/graph-explorer';
import '@/components/ontology/ontology-dashboard.css';
import '../instance-browser.css';
import './graph-explorer.css';

const number = (value: number | null | undefined) => (value == null ? '—' : value.toLocaleString());
const palette = ['#3b82f6', '#0891b2', '#8b5cf6', '#d97706', '#16a34a', '#db2777'];

function Dashboard({
  data,
  onGraph,
  onInstances,
}: {
  data: ExplorerOverview;
  onGraph: (uri: string) => void;
  onInstances: () => void;
}) {
  const k = data.kpis;
  const multi = data.selected_graphs.length > 1;
  const excluded = data.excluded ?? {};
  const graphLabel = (uri: string) => data.graphs.find((g) => g.uri === uri)?.label ?? uri;
  // A consolidated KPI may leave out graphs where that metric could not be read.
  const pendingSet = new Set(data.pending ?? []);
  const unreadable = data.unreadable_predicates ?? {};
  const unreadableCount = Object.values(unreadable).reduce((n, list) => n + list.length, 0);
  const excludedNote = (key: keyof ExplorerKpis) => {
    const graphs = excluded[key] ?? [];
    const counting = graphs.filter((uri) => pendingSet.has(uri)).map(graphLabel);
    const failed = graphs.filter((uri) => !pendingSet.has(uri)).map(graphLabel);
    const parts = [
      counting.length ? `counting ${counting.join(', ')}…` : '',
      failed.length ? `excl. ${failed.join(', ')}` : '',
      (key === 'relations' || key === 'literal_values') && unreadableCount
        ? `excl. ${unreadableCount} unreadable predicate${unreadableCount > 1 ? 's' : ''}`
        : '',
    ];
    return parts.filter(Boolean).join(' · ');
  };
  const sameScope =
    (excluded.instances ?? []).join() === (excluded.labeled_instances ?? []).join();
  const coverage =
    k.instances && k.labeled_instances != null && sameScope
      ? Math.round((k.labeled_instances / k.instances) * 100)
      : null;
  const partialGraphs = [...new Set(Object.values(excluded).flat())].filter(
    (uri) => !pendingSet.has(uri),
  );
  const pending = data.pending ?? [];
  const snapshotTimes = data.graph_metrics
    .map((g) => g.computed_at)
    .filter((t): t is string => !!t)
    .sort();
  const oldestSnapshot = snapshotTimes[0] ? new Date(snapshotTimes[0]) : null;
  const metrics = [
    [
      'Instances',
      number(k.instances),
      multi
        ? 'Typed IRIs per graph, summed across the selected graphs. Schema declarations and blank nodes are excluded.'
        : 'Distinct typed IRIs in this graph. Schema declarations and blank nodes are excluded.',
      'instances',
    ],
    [
      'Triples',
      number(k.triples),
      'Stored triples across the selected named graphs. A triple in two graphs counts twice.',
      'triples',
    ],
    [
      'Named graphs',
      number(data.selected_graphs.length),
      'Named graphs included in this dashboard, including empty graphs.',
      null,
    ],
    [
      'Label coverage',
      coverage === null ? '—' : `${coverage}%`,
      'Instances with a non-empty RDFS label in their graph.',
      'labeled_instances',
    ],
  ] as const;
  const breakdown = [
    ['Classes', 'classes', 'Distinct classes used by instances (unique across graphs).'],
    ['Named individuals', 'named_individuals', 'Instances explicitly declared owl:NamedIndividual.'],
    ['Predicates', 'predicates', 'Distinct predicates used in the selected graphs (unique across graphs).'],
    ['Relationships', 'relations', 'Triples with an IRI object, excluding rdf:type.'],
    ['Literal values', 'literal_values', 'Triples with a literal object.'],
  ] as const;
  const graphTiles =
    data.graph_metrics.length > 0
      ? data.graph_metrics
      : data.graphs.map((g) => ({
          ...g,
          triples: 0,
          instances: 0,
          named_individuals: 0,
          labeled_instances: 0,
          classes: 0,
          predicates: 0,
          relations: 0,
          literal_values: 0,
        }));
  const roles = [...new Set(graphTiles.map((g) => g.role_label))].sort();
  return (
    <div className="ontology-dashboard">
      <main className="ontology-dashboard-main">
        <header className="ontology-dashboard-header">
          <div className="ontology-dashboard-heading">
            <h1>Knowledge Graph</h1>
            <span>Explorer · {number(data.selected_graphs.length)} graphs</span>
          </div>
          <p>
            Explore the data behind your ontology. Choose a graph, then a class to browse its
            instances.
          </p>
        </header>
        <div className="ontology-dashboard-table-heading">
          <h2>Overview</h2>
          <span>
            {multi ? `Consolidated from ${data.selected_graphs.length} graph snapshots` : 'Selected graph'}
            {oldestSnapshot && ` · as of ${oldestSnapshot.toLocaleTimeString()}`}
          </span>
        </div>
        {pending.length > 0 && (
          <p className="ontology-dashboard-empty" role="status">
            Counting {pending.length} of {data.selected_graphs.length} graphs… Totals below cover the
            graphs already counted and update automatically.
          </p>
        )}
        {partialGraphs.length > 0 && (
          <p className="ontology-dashboard-empty" role="status">
            Some totals leave out {partialGraphs.map(graphLabel).join(', ')}: the triple store could
            not read that part of the data. Affected metrics are marked “excl.”.
          </p>
        )}
        <section
          className="ontology-dashboard-metrics ontology-dashboard-summary"
          aria-label="Overview"
        >
          {metrics.map(([label, value, title, key], i) => (
            <div className="ontology-dashboard-metric" key={label} title={title}>
              <span>{label}</span>
              <strong>
                {i === 0 ? (
                  <button type="button" onClick={onInstances} title="Browse all instances">
                    {value}
                  </button>
                ) : (
                  value
                )}
              </strong>
              <span className="ontology-dashboard-metric-note">
                {(key && excludedNote(key)) ||
                  (i === 3
                    ? `${number(k.labeled_instances)} labeled · ${number(
                        k.instances == null || k.labeled_instances == null || !sameScope
                          ? null
                          : k.instances - k.labeled_instances,
                      )} missing`
                    : i === 0
                      ? multi
                        ? 'Summed across graphs'
                        : 'Unique in this graph'
                      : i === 1
                        ? 'Across named graphs'
                        : 'In current selection')}
              </span>
            </div>
          ))}
        </section>
        <div className="ontology-dashboard-table-heading">
          <h2>Breakdown</h2>
          <span>Instances and statements</span>
        </div>
        <section
          className="ontology-dashboard-metrics graph-explorer-detail-kpis"
          aria-label="Detailed metrics"
        >
          {breakdown.map(([label, key, title]) => (
            <div className="ontology-dashboard-metric" key={label} title={title}>
              <span>{label}</span>
              <strong>{number(k[key])}</strong>
              {excludedNote(key) && (
                <span className="ontology-dashboard-metric-note">{excludedNote(key)}</span>
              )}
            </div>
          ))}
        </section>
        <div className="ontology-dashboard-table-heading">
          <h2>Named graphs</h2>
          <span>Select a graph to explore its classes and instances</span>
        </div>
        {graphTiles.length === 0 ? (
          <p className="ontology-dashboard-empty">
            No named graphs are available. Use File → Create New Graph to get started.
          </p>
        ) : (
          roles.map((role, roleIndex) => (
            <section className="ontology-dashboard-group" key={role}>
              <h3>
                {role || 'Graphs'}
                <span>{graphTiles.filter((g) => g.role_label === role).length}</span>
              </h3>
              <div className="ontology-dashboard-grid">
                {graphTiles
                  .filter((g) => g.role_label === role)
                  .map((graph, index) => (
                    <button
                      type="button"
                      className="ontology-dashboard-tile"
                      key={graph.uri}
                      title={graph.uri}
                      style={
                        { '--tile-color': palette[roleIndex % palette.length] } as CSSProperties
                      }
                      onClick={() => onGraph(graph.uri)}
                    >
                      <span className="ontology-dashboard-tile-index">
                        <span>{String(index + 1).padStart(2, '0')}</span>
                        <span>Graph</span>
                      </span>
                      <span className="graph-explorer-tile-symbol">
                        {graph.label
                          .split(/[^\p{L}\p{N}]+/u)
                          .filter(Boolean)
                          .slice(0, 2)
                          .map((w) => w[0])
                          .join('')
                          .toUpperCase() || 'G'}
                      </span>
                      <strong>{graph.label}</strong>
                      {'pending' in graph && graph.pending ? (
                        <span className="ontology-dashboard-tile-meta">
                          <span>Computing…</span>
                        </span>
                      ) : (
                        <>
                          <span className="ontology-dashboard-tile-meta">
                            <span>{number(graph.instances)} instances</span>
                          </span>
                          <span className="ontology-dashboard-tile-meta">
                            <span>{number(graph.triples)} triples</span>
                          </span>
                        </>
                      )}
                      {'unavailable' in graph && graph.unavailable?.length ? (
                        <span
                          className="ontology-dashboard-tile-meta"
                          title={`Unavailable: ${graph.unavailable.join(', ')}`}
                        >
                          <span>Incomplete metrics</span>
                        </span>
                      ) : null}
                    </button>
                  ))}
              </div>
            </section>
          ))
        )}
        <p className="ontology-dashboard-footnote">
          Instance counts are unique by IRI within each graph. Across several graphs they are summed,
          so an instance present in two graphs counts twice. Classes and predicates stay unique across
          graphs. Graph statistics are snapshots refreshed every 5 minutes.
        </p>
      </main>
    </div>
  );
}

function InstanceTable({
  workspaceId,
  graphs,
  classes,
  catalog,
  allClasses,
  revision,
  view,
  onViewChange,
}: {
  workspaceId: string;
  graphs: string[];
  classes: string[];
  catalog: ExplorerOverview['graphs'];
  allClasses: ExplorerOverview['classes'];
  revision: number;
  view: ExplorerView;
  onViewChange: (view: ExplorerView) => void;
}) {
  const [page, setPage] = useState(0);
  // Keep only presentation widths while the table remounts for paging/loading.
  const columnWidthsRef = useRef<Record<string, number>>({});
  const [search, setSearch] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [selected, setSelected] = useState<ApiDiscoveryInstance | null>(null);
  const request = useGraphRequest<ExplorerNetworkData>(
    view === 'network' ? 'explorer/network' : 'explorer/instances',
    {
      workspace_id: workspaceId,
      graph_uris: graphs,
      class_uris: classes,
      search: submitted,
      offset: page * 50,
      limit: 50,
    },
    view !== 'details',
  );
  useEffect(() => {
    setSelected(null);
    if (view === 'network') void preloadExplorerNetwork().catch(() => {});
  }, [view]);
  // External mutations refresh the table as well as the dashboard.
  useEffect(() => {
    const refresh = () => {
      setSelected(null);
    };
    window.addEventListener('graph-cache-refresh', refresh);
    return () => window.removeEventListener('graph-cache-refresh', refresh);
  }, []);
  const labels = Object.fromEntries(catalog.map((g) => [g.uri, g.label]));
  const title =
    classes.length === 1
      ? allClasses.find((c) => c.uri === classes[0])?.label || classes[0].split(/[/#]/).pop() || 'Class instances'
      : classes.length
        ? `${classes.length} classes`
        : 'All instances';
  const graphLabel =
    graphs.length === 1
      ? labels[graphs[0]] || 'Selected graph'
      : graphs.length
        ? `${graphs.length} graphs`
        : 'All Graphs';
  const items = request.data?.items || [];
  return <>
    <nav className="graph-explorer-canvas-tabs" aria-label="Explorer views">
      {([['instances', 'Instances'], ['network', 'Network'], ['details', 'Details']] as const).map(([key, label]) => (
        <button key={key} type="button" aria-current={view === key ? 'page' : undefined}
          disabled={key === 'details' && classes.length !== 1}
          title={key === 'details' && classes.length !== 1 ? 'Select one class to see its definition' : undefined}
          onClick={() => onViewChange(key)}>{label}</button>
      ))}
    </nav>
    {view === 'details' ? <ExplorerClassDetails workspaceId={workspaceId} classUri={classes[0]} classInfo={allClasses.find(item => item.uri === classes[0])} /> : (
    <div className="graph-explorer-content" data-revision={revision}>
      <main className="graph-explorer-instance-main">
        <header className="graph-explorer-instance-heading">
          <div>
            <h1>{title}</h1>
            <p>{graphLabel} · {view === 'network' ? 'instances and their relationships' : 'select an instance to inspect'}</p>
          </div>
          <form
            className="graph-explorer-search"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted(search.trim());
              setPage(0);
              setSelected(null);
            }}
          >
            <Search size={14} />
            <input
              aria-label="Search instances"
              placeholder="Search instances, press Enter…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                if (!e.target.value) {
                  setSubmitted('');
                  setPage(0);
                  setSelected(null);
                }
              }}
            />
          </form>
        </header>
        <div className="graph-explorer-table" aria-busy={request.loading}>
          {request.loading ? (
            <p className="graph-explorer-message" role="status">
              Loading instances…
            </p>
          ) : request.error ? (
            <p className="graph-explorer-message" role="alert">
              {request.error}
              <button onClick={request.retry}>Retry</button>
            </p>
          ) : !items.length ? (
            <p className="graph-explorer-message">
              {submitted ? 'No instances match this search.' : 'No instances in this selection.'}
            </p>
          ) : view === 'network' ? (
            <ExplorerNetwork data={request.data!} selected={selected} onSelect={setSelected}
              scopeKey={JSON.stringify([workspaceId, graphs, classes, submitted, page])} />
          ) : (
            <IndividualsTable
              instances={items}
              workspaceId={workspaceId}
              graphUri=""
              graphLabels={labels}
              columnWidthsRef={columnWidthsRef}
              onDeleted={() => request.retry()}
              readOnly
              onOpen={setSelected}
            />
          )}
        </div>
        <footer className="graph-explorer-instance-footer">
          <span>
            {request.loading
              ? 'Loading…'
              : request.error
                ? 'Unavailable'
                : `${items.length ? page * 50 + 1 : 0}–${page * 50 + items.length} graph memberships`}{' '}
            {view === 'network'
              ? `· ${request.data?.neighbors?.length || 0} related resources · ${request.data?.relations?.length || 0} relationships${request.data?.relations_truncated ? ' (first 200 shown)' : ''}`
              : '· one row per instance per graph'}
          </span>
          <button
            type="button"
            disabled={!page || request.loading}
            onClick={() => {
              setPage((p) => p - 1);
              setSelected(null);
            }}
          >
            Previous
          </button>
          <button
            type="button"
            disabled={request.loading || !!request.error || !request.data?.has_more}
            onClick={() => {
              setPage((p) => p + 1);
              setSelected(null);
            }}
          >
            Next
          </button>
        </footer>
      </main>
      {selected?.graph_uri && (
        <aside className="graph-instance-panel">
          <InstanceInspector
            key={`${selected.graph_uri}:${selected.uri}`}
            instance={selected}
            graphUri={selected.graph_uri}
            graphLabel={labels[selected.graph_uri]}
            workspaceId={workspaceId}
            onClose={() => setSelected(null)}
            onSelectInstance={(instance) =>
              setSelected({ ...instance, properties: {}, graph_uri: selected.graph_uri })
            }
          />
        </aside>
      )}
    </div>
    )}
  </>;
}

export default function GraphExplorerPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const router = useRouter();
  const query = useSearchParams().toString();
  const scope = explorerScope(query);
  const request = useGraphExplorer(workspaceId, scope.graphs);
  const overview = useGraphRequest<ExplorerOverview>('explorer/overview', { workspace_id: workspaceId, graph_uris: scope.graphs }, scope.dashboard);
  // Poll quietly while the server is still computing graph snapshots, backing off.
  const pollAttempt = useRef(0);
  const pendingSnapshots = overview.data?.pending?.length ?? 0;
  const refreshOverview = overview.refresh;
  useEffect(() => {
    if (!pendingSnapshots) {
      pollAttempt.current = 0;
      return;
    }
    const timer = window.setTimeout(refreshOverview, pendingPollDelay(pollAttempt.current++));
    return () => window.clearTimeout(timer);
  }, [overview.data, pendingSnapshots, refreshOverview]);
  const navigate = (changes: Record<string, string | string[] | null>) =>
    router.push(`/workspace/${workspaceId}/graph/explorer?${explorerQuery(query, changes)}`, {
      scroll: false,
    });
  const classes = scope.activeClass ? [scope.activeClass] : scope.classes;
  return (
    <div className="graph-explorer-page">
      <GraphHeader title="Knowledge Graph" />
      {scope.dashboard ? (
        overview.loading ? <div className="ontology-dashboard-state" role="status">Loading dashboard…</div>
        : overview.error ? <div className="ontology-dashboard-state" role="alert">{overview.error}<button onClick={overview.retry}>Retry</button></div>
        : overview.data && <Dashboard data={overview.data}
            onGraph={uri => navigate({ graph: [uri], class: null, classFilter: null, view: 'instances' })}
            onInstances={() => navigate({ view: 'instances', class: null, classFilter: null })} />
      ) : (
        <InstanceTable
          key={JSON.stringify([workspaceId, scope.graphs, classes])}
          workspaceId={workspaceId} graphs={scope.graphs} classes={classes}
          catalog={request.data?.graphs || []} allClasses={request.data?.classes || []}
          revision={request.revision}
          view={scope.view === 'details' && classes.length !== 1 ? 'instances' : scope.view}
          onViewChange={view => navigate({ view })}
        />
      )}
    </div>
  );
}
