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
import { explorerQuery, explorerScope, type ExplorerView, type ExplorerOverview } from '@/lib/graph-explorer';
import '@/components/ontology/ontology-dashboard.css';
import '../instance-browser.css';
import './graph-explorer.css';

const number = (value: number) => value.toLocaleString();
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
  const coverage = k.instances ? Math.round((k.labeled_instances / k.instances) * 100) : null;
  const metrics = [
    [
      'Instances',
      number(k.instances),
      'Distinct typed IRIs across the selected graphs. Schema declarations and blank nodes are excluded.',
    ],
    [
      'Triples',
      number(k.triples),
      'Stored triples across the selected named graphs. A triple in two graphs counts twice.',
    ],
    [
      'Named graphs',
      number(data.selected_graphs.length),
      'Named graphs included in this dashboard, including empty graphs.',
    ],
    [
      'Label coverage',
      coverage === null ? '—' : `${coverage}%`,
      'Instances with a non-empty RDFS label in at least one selected graph.',
    ],
  ];
  const breakdown = [
    ['Classes', k.classes, 'Distinct classes used by instances.'],
    [
      'Named individuals',
      k.named_individuals,
      'Instances explicitly declared owl:NamedIndividual.',
    ],
    ['Predicates', k.predicates, 'Distinct predicates used in the selected graphs.'],
    ['Relationships', k.relations, 'Triples with an IRI object, excluding rdf:type.'],
    ['Literal values', k.literal_values, 'Triples with a literal object.'],
  ] as const;
  const roles = [...new Set(data.graph_metrics.map((g) => g.role_label))].sort();
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
          <span>Selected graphs</span>
        </div>
        <section
          className="ontology-dashboard-metrics ontology-dashboard-summary"
          aria-label="Overview"
        >
          {metrics.map(([label, value, title], i) => (
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
                {i === 3
                  ? `${number(k.labeled_instances)} labeled · ${number(k.instances - k.labeled_instances)} missing`
                  : i === 0
                    ? 'Unique across graphs'
                    : i === 1
                      ? 'Across named graphs'
                      : 'In current selection'}
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
          {breakdown.map(([label, value, title]) => (
            <div className="ontology-dashboard-metric" key={label} title={title}>
              <span>{label}</span>
              <strong>{number(value)}</strong>
            </div>
          ))}
        </section>
        <div className="ontology-dashboard-table-heading">
          <h2>Named graphs</h2>
          <span>Select a graph to explore its classes and instances</span>
        </div>
        {data.graph_metrics.length === 0 ? (
          <p className="ontology-dashboard-empty">
            No named graphs are available. Use File → Create New Graph to get started.
          </p>
        ) : (
          roles.map((role, roleIndex) => (
            <section className="ontology-dashboard-group" key={role}>
              <h3>
                {role || 'Graphs'}
                <span>{data.graph_metrics.filter((g) => g.role_label === role).length}</span>
              </h3>
              <div className="ontology-dashboard-grid">
                {data.graph_metrics
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
                      <span className="ontology-dashboard-tile-meta">
                        <span>{number(graph.instances)} instances</span>
                      </span>
                      <span className="ontology-dashboard-tile-meta">
                        <span>{number(graph.triples)} triples</span>
                      </span>
                    </button>
                  ))}
              </div>
            </section>
          ))
        )}
        <p className="ontology-dashboard-footnote">
          Instance counts are unique by IRI. One instance may belong to several classes or graphs;
          their individual counts do not add up to the unique total.
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
