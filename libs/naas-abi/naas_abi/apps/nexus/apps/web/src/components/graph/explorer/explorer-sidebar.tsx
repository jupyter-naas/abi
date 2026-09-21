'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Box, ChevronRight, LayoutDashboard, Search, X } from 'lucide-react';
import { OntologyMultiPicker } from '@/components/shell/sidebar/ontology-multi-picker';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { useOntologyIconsStore } from '@/stores/ontology-icons';
import { useOntologyTreeKeyboard } from '@/hooks/use-ontology-tree-keyboard';
import {
  buildDictionaryTree,
  filterDictionaryTree,
  type DictionaryNode,
} from '@/lib/ontology-dictionary-tree';
import {
  classTerms,
  explorerQuery,
  explorerScope,
  explorerShowsGraphHint,
  groupSearchHitsByClass,
  toggleValue,
} from '@/lib/graph-explorer';
import { useGraphExplorer, useGraphExplorerStore, useWorkspaceGraphList } from '@/stores/graph-explorer';
import { useGraphSearch } from '@/hooks/use-graph-search';
import { individualHref } from '@/lib/graph-instance-browser';
import { ExplorerClassInstances } from './explorer-class-instances';
import './graph-explorer.css';

export function GraphExplorerSidebar({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const query = useSearchParams().toString();
  const path = usePathname();
  const latestQuery = useRef({ observed: query, value: query });
  if (latestQuery.current.observed !== query)
    latestQuery.current = { observed: query, value: query };
  const scope = explorerScope(query);
  const treeKeyboard = useOntologyTreeKeyboard();
  const [search, setSearch] = useState(() => new URLSearchParams(query).get('find') || '');
  const hits = useGraphSearch(workspaceId, scope.graphs, scope.classes, search);
  const searching = search.trim().length > 0;
  useEffect(() => { setSearch(new URLSearchParams(query).get('find') || ''); }, [workspaceId, query]);
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const [openClasses, setOpenClasses] = useState<Set<string>>(new Set());
  const list = useWorkspaceGraphList(workspaceId);
  const request = useGraphExplorer(workspaceId, scope.graphs);
  const workspaceGraphs = useMemo(() => {
    const seen = new Set<string>();
    const merged: typeof list.graphs = [];
    for (const graph of [...list.graphs, ...(request.data?.graphs || [])]) {
      if (seen.has(graph.uri)) continue;
      seen.add(graph.uri);
      merged.push(graph);
    }
    return merged;
  }, [list.graphs, request.data?.graphs]);
  const loadIcons = useOntologyIconsStore((s) => s.load);
  useEffect(() => {
    void loadIcons(workspaceId);
  }, [workspaceId, loadIcons]);
  const graphKey = JSON.stringify(scope.graphs);
  useEffect(() => {
    const refresh = () =>
      void useGraphExplorerStore
        .getState()
        .load(workspaceId, JSON.parse(graphKey) as string[], true);
    window.addEventListener('graph-cache-refresh', refresh);
    window.addEventListener('graph-list-update', refresh);
    return () => {
      window.removeEventListener('graph-cache-refresh', refresh);
      window.removeEventListener('graph-list-update', refresh);
    };
  }, [workspaceId, graphKey]);
  const classes = request.data?.classes || [];
  const classesKey = JSON.stringify(scope.classes);
  const scopedClasses = useMemo(() => {
    const all = request.data?.classes || [];
    const selected = JSON.parse(classesKey) as string[];
    if (!selected.length) return all;
    const keep = new Set(selected);
    const byId = new Map(all.map((c) => [c.uri, c]));
    function ancestors(uri: string) {
      for (const parent of byId.get(uri)?.parents || [])
        if (!keep.has(parent)) {
          keep.add(parent);
          ancestors(parent);
        }
    }
    selected.forEach(ancestors);
    return all.filter((c) => keep.has(c.uri));
  }, [request.data, classesKey]);
  const tree = useMemo(
    () =>
      scope.hierarchy
        ? filterDictionaryTree(buildDictionaryTree(classTerms(scopedClasses)), search)
        : [],
    [scopedClasses, search, scope.hierarchy],
  );
  const alphabetical = scopedClasses.filter(
    (c) =>
      c.count > 0 &&
      (!scope.classes.length || scope.classes.includes(c.uri)) &&
      `${c.label} ${c.uri}`.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const root = `/workspace/${workspaceId}/graph/explorer`;
  const navigate = (
    changes:
      | Record<string, string | string[] | null>
      | ((query: string) => Record<string, string | string[] | null>),
  ) => {
    const current = latestQuery.current.value;
    const next = explorerQuery(current, typeof changes === 'function' ? changes(current) : changes);
    latestQuery.current.value = next;
    router.push(`${root}?${next}`, { scroll: false });
  };
  const select = (uri: string) => navigate({ class: uri, view: scope.dashboard ? 'instances' : scope.view, page: null });
  const selectedUri = new URLSearchParams(query).get('selected');
  const graphLabels = Object.fromEntries(workspaceGraphs.map((g) => [g.uri, g.label]));
  const workspaceGraphCount = workspaceGraphs.length;
  const openInstance = (instance: { uri: string; graph_uri: string; class_uri: string }) => {
    router.push(
      `${individualHref(workspaceId, instance.graph_uri, instance.class_uri, instance.uri)}${
        searching ? `&find=${encodeURIComponent(search)}` : ''
      }`,
      { scroll: false },
    );
  };
  const toggleClass = (uri: string) =>
    setOpenClasses((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  const searchGroups = useMemo(() => groupSearchHitsByClass(hits.results), [hits.results]);
  const showSearchGraphHint = explorerShowsGraphHint(
    scope.graphs,
    workspaceGraphCount,
    searchGroups.flatMap((group) => group.instances.map((hit) => hit.graph_uri)),
  );
  useEffect(() => {
    const selected = JSON.parse(classesKey) as string[];
    setOpenClasses((prev) => {
      let changed = false;
      const next = new Set(prev);
      for (const uri of selected) {
        if (!next.has(uri)) {
          next.add(uri);
          changed = true;
        }
      }
      if (scope.activeClass && !next.has(scope.activeClass)) {
        next.add(scope.activeClass);
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [classesKey, scope.activeClass]);
  useEffect(() => {
    if (!searching || hits.loading) return;
    setOpenClasses((prev) => {
      const next = new Set(prev);
      const classOnly = searchGroups.filter((group) => !group.instances.length);
      for (const group of searchGroups) {
        if (group.instances.length) next.add(group.class_uri);
      }
      if (classOnly.length === 1) next.add(classOnly[0].class_uri);
      return next;
    });
  }, [searching, hits.loading, searchGroups]);
  const graphPickerProps = {
    loading: list.loading && workspaceGraphs.length === 0,
    error: list.error,
  };
  const classPickerProps = { loading: request.loading, error: request.error };
  const graphLabel =
    scope.graphs.length === 0
      ? 'All Graphs'
      : scope.graphs.length === 1
        ? workspaceGraphs.find((g) => g.uri === scope.graphs[0])?.label || '1 graph'
        : `${scope.graphs.length} graphs`;
  const classLabel = !scope.classes.length
    ? 'All Classes'
    : scope.classes.length === 1
      ? classes.find((c) => c.uri === scope.classes[0])?.label || '1 class'
      : `${scope.classes.length} classes`;
  const isExplorer = path.endsWith('/explorer');
  const instances = (uri: string, label: string) =>
    openClasses.has(uri) ? (
      <ExplorerClassInstances
        workspaceId={workspaceId}
        graphs={scope.graphs}
        classUri={uri}
        classLabel={label}
        selectedUri={selectedUri}
        graphLabels={graphLabels}
        workspaceGraphCount={workspaceGraphCount}
        onOpen={openInstance}
      />
    ) : null;
  function renderNode(node: DictionaryNode, parentPath: string): React.ReactNode {
    const uri = node.term?.id || node.id.replace(/^entity:/, '');
    const key = `${parentPath}/${uri}`;
    const childrenOpen = search !== '' || !closed.has(key);
    const count = classes.find((c) => c.uri === uri)?.count || 0;
    const instancesOpen = openClasses.has(uri);
    const canExpand = node.children.length > 0 || count > 0;
    return (
      <li key={key} data-ontology-tree-row>
        <div className="graph-explorer-tree-row">
          {canExpand ? (
            <button
              type="button"
              className="graph-explorer-disclosure"
              data-ontology-tree-toggle
              aria-label={`${(node.children.length ? childrenOpen : instancesOpen) ? 'Collapse' : 'Expand'} ${node.name}`}
              aria-expanded={node.children.length ? childrenOpen : instancesOpen}
              onClick={() => {
                if (node.children.length) {
                  setClosed((prev) => {
                    const next = new Set(prev);
                    if (next.has(key)) next.delete(key);
                    else next.add(key);
                    return next;
                  });
                  return;
                }
                if (count > 0) toggleClass(uri);
              }}
            >
              <ChevronRight
                size={12}
                style={{
                  transform: (node.children.length ? childrenOpen : instancesOpen)
                    ? 'rotate(90deg)'
                    : undefined,
                }}
              />
            </button>
          ) : (
            <span className="graph-explorer-disclosure" />
          )}
          <button
            type="button"
            data-ontology-tree-item={key}
            data-ontology-tree-select
            aria-current={isExplorer && scope.activeClass === uri ? 'page' : undefined}
            onClick={() => select(uri)}
            title={uri}
          >
            <OntologyTopicIcon subject={{ id: uri, name: node.name, type: 'entity' }} />
            <span>{node.name}</span>
            <small>{count || '—'}</small>
          </button>
        </div>
        {childrenOpen && node.children.length > 0 && (
          <ul>{node.children.map((child) => renderNode(child, key))}</ul>
        )}
        {instances(uri, node.name)}
      </li>
    );
  }
  return (
    <div className="graph-explorer-sidebar">
      <div className="graph-explorer-filters">
        <button
          type="button"
          className="graph-explorer-dashboard-link"
          aria-current={isExplorer && scope.dashboard ? 'page' : undefined}
          onClick={() => navigate({ view: null, class: null, classFilter: null, page: null })}
        >
          <LayoutDashboard size={14} />
          Dashboard
        </button>
        <OntologyMultiPicker
          {...graphPickerProps}
          items={workspaceGraphs.map((g) => ({
            value: g.uri,
            label: g.label,
            title: g.uri,
            detail: g.role_label,
          }))}
          value={scope.graphs}
          noun="graphs"
          allLabel="All Graphs"
          label={graphLabel}
          onClear={() => navigate({ graph: null, class: null, page: null })}
          onToggle={(uri) =>
            navigate((current) => ({
              graph: toggleValue(explorerScope(current).graphs, uri),
              class: null,
              page: null,
            }))
          }
        />
        <OntologyMultiPicker
          {...classPickerProps}
          items={classes
            .filter((c) => c.count > 0)
            .map((c) => ({
              value: c.uri,
              label: c.label,
              title: c.uri,
              detail: `${c.count.toLocaleString()} instances`,
            }))}
          value={scope.classes}
          noun="classes"
          allLabel="All Classes"
          label={classLabel}
          onClear={() =>
            navigate({ classFilter: null, class: null, view: 'instances', page: null })
          }
          onToggle={(uri) =>
            navigate((current) => ({
              classFilter: toggleValue(explorerScope(current).classes, uri),
              class: null,
              view: 'instances',
              page: null,
            }))
          }
        />
      </div>
      <label className="graph-explorer-search">
        <Search size={14} />
        <input
          aria-label="Search instances and classes"
          placeholder="Search instances and classes…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setSearch('');
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              document.querySelector<HTMLButtonElement>('.graph-explorer-search-results button[data-ontology-tree-select], .graph-explorer-class-list button[data-ontology-tree-select]')?.focus();
            }
          }}
        />
        {searching && <button type="button" aria-label="Clear search" onClick={() => setSearch('')}><X size={12} /></button>}
      </label>
      {searching ? (
        <section {...treeKeyboard} className="graph-explorer-class-list graph-explorer-search-results" aria-label="Search results" aria-busy={hits.loading}>
          {search.trim().length < 2 ? <p className="graph-explorer-message">Type at least two characters.</p> : hits.loading ? <p className="graph-explorer-message" role="status">Searching…</p> : hits.error ? <p className="graph-explorer-message" role="alert">{hits.error} <button onClick={hits.retry}>Retry</button></p> : (
            <>
              {searchGroups.length ? (
                <ul>
                  {searchGroups.map((group) => {
                    const expanded = openClasses.has(group.class_uri);
                    const hasChildren = group.instances.length > 0 || group.instance_count > 0;
                    return (
                      <li key={group.class_uri} data-ontology-tree-row>
                        <div className="graph-explorer-tree-row">
                          {hasChildren ? (
                            <button
                              type="button"
                              className="graph-explorer-disclosure"
                              data-ontology-tree-toggle
                              aria-label={`${expanded ? 'Collapse' : 'Expand'} ${group.class_label}`}
                              aria-expanded={expanded}
                              onClick={() => toggleClass(group.class_uri)}
                            >
                              <ChevronRight
                                size={12}
                                style={{ transform: expanded ? 'rotate(90deg)' : undefined }}
                              />
                            </button>
                          ) : (
                            <span className="graph-explorer-disclosure" />
                          )}
                          <button
                            type="button"
                            data-ontology-tree-item={group.class_uri}
                            data-ontology-tree-select
                            aria-current={isExplorer && scope.activeClass === group.class_uri ? 'page' : undefined}
                            title={group.class_uri}
                            onClick={() =>
                              navigate({
                                class: group.class_uri,
                                selected: null,
                                view: 'instances',
                                page: null,
                                find: search,
                              })
                            }
                          >
                            <OntologyTopicIcon
                              subject={{ id: group.class_uri, name: group.class_label, type: 'entity' }}
                            />
                            <span>{group.class_label}</span>
                            <small>{group.instance_count || group.instances.length || '—'}</small>
                          </button>
                        </div>
                        {expanded &&
                          (group.instances.length ? (
                            <ul>
                              {group.instances.map((hit) => (
                                <li key={`${hit.graph_uri}:${hit.uri}`} data-ontology-tree-row>
                                  <div className="graph-explorer-tree-row">
                                    <button
                                      type="button"
                                      data-ontology-tree-item={`${hit.graph_uri}:${hit.uri}`}
                                      data-ontology-tree-select
                                      aria-current={
                                        selectedUri === hit.uri &&
                                        (!scope.graphs.length || scope.graphs.includes(hit.graph_uri))
                                          ? 'page'
                                          : undefined
                                      }
                                      title={hit.uri}
                                      onClick={() => openInstance(hit)}
                                    >
                                      <OntologyTopicIcon
                                        subject={{
                                          id: hit.class_uri,
                                          name: hit.class_label,
                                          type: 'entity',
                                        }}
                                      />
                                      <span>{hit.label}</span>
                                      {showSearchGraphHint && (
                                        <small className="graph-explorer-graph-hint">
                                          {graphLabels[hit.graph_uri] || hit.graph_uri}
                                        </small>
                                      )}
                                    </button>
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <ExplorerClassInstances
                              workspaceId={workspaceId}
                              graphs={scope.graphs}
                              classUri={group.class_uri}
                              classLabel={group.class_label}
                              selectedUri={selectedUri}
                              graphLabels={graphLabels}
                              workspaceGraphCount={workspaceGraphCount}
                              onOpen={openInstance}
                            />
                          ))}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="graph-explorer-message">
                  No matching instances or classes in the selected graphs.
                </p>
              )}
            </>
          )}
        </section>
      ) : <>
      <div className="graph-explorer-tabs" aria-label="Class list layout">
        {[
          ['az', 'A-Z'],
          ['hierarchy', 'Hierarchy'],
        ].map(([value, label]) => (
          <button
            type="button"
            key={value}
            aria-pressed={scope.hierarchy === (value === 'hierarchy')}
            onClick={() => navigate({ list: value })}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="graph-explorer-list-count">
        {request.loading
          ? 'Loading classes…'
          : `${classes.filter((c) => c.count > 0).length.toLocaleString()} classes`}
      </p>
      {request.error ? (
        <p className="graph-explorer-message" role="alert">
          {request.error} <button onClick={request.retry}>Retry</button>
        </p>
      ) : (
        <section {...treeKeyboard} className="graph-explorer-class-list" aria-label="Classes and instances">
          {scope.hierarchy ? (
            <ul>{tree.map((node) => renderNode(node, ''))}</ul>
          ) : (
            <ul>
              {alphabetical.map((c) => {
                const expanded = openClasses.has(c.uri);
                return (
                  <li key={c.uri} data-ontology-tree-row>
                    <div className="graph-explorer-tree-row">
                      {c.count > 0 ? (
                        <button
                          type="button"
                          className="graph-explorer-disclosure"
                          data-ontology-tree-toggle
                          aria-label={`${expanded ? 'Collapse' : 'Expand'} ${c.label}`}
                          aria-expanded={expanded}
                          onClick={() => toggleClass(c.uri)}
                        >
                          <ChevronRight
                            size={12}
                            style={{ transform: expanded ? 'rotate(90deg)' : undefined }}
                          />
                        </button>
                      ) : (
                        <span className="graph-explorer-disclosure" />
                      )}
                      <button
                        type="button"
                        data-ontology-tree-item={c.uri}
                        data-ontology-tree-select
                        aria-current={isExplorer && scope.activeClass === c.uri ? 'page' : undefined}
                        onClick={() => select(c.uri)}
                        title={c.uri}
                      >
                        <OntologyTopicIcon subject={{ id: c.uri, name: c.label, type: 'entity' }} />
                        <span>{c.label}</span>
                        <small>{c.count.toLocaleString()}</small>
                      </button>
                    </div>
                    {instances(c.uri, c.label)}
                  </li>
                );
              })}
            </ul>
          )}
          {!request.loading &&
            (scope.hierarchy ? tree.length === 0 : alphabetical.length === 0) && (
              <p className="graph-explorer-message">
                <Box size={14} />
                No matching classes.
              </p>
            )}
        </section>
      )}
      </>}
    </div>
  );
}
