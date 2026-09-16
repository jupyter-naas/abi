'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ChevronRight, Search } from 'lucide-react';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useOntologyStore } from '@/stores/ontology';
import { useWorkspaceStore } from '@/stores/workspace';
import { cn } from '@/lib/utils';
import { buildDictionaryTree, filterDictionaryTree, dictionaryKindLabel, type DictionaryNode, type DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { dictionaryFilter, dictionaryFilterRoute, termTabs, kindForView, termRoute } from '@/lib/ontology-navigation';
import { dictionaryFiles, dictionaryFilesRoute, filterTermsByFiles, type DictionaryFile } from '@/lib/ontology-file-filter';
import { getWorkspacePath } from './utils';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { OntologySystemTree } from '@/components/ontology/ontology-system-tree';
import { OntologyFilePicker } from './ontology-file-picker';
import { useOntologyTreeKeyboard } from '@/hooks/use-ontology-tree-keyboard';

export function OntologyDictionary({files, filesLoading, filesError}: {
  files: DictionaryFile[]; filesLoading: boolean; filesError: string | null;
}) {
  const keyboard = useOntologyTreeKeyboard();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const refresh = useOntologyStore(state => state.graphRefreshTrigger);
  const dictionary = useOntologyDictionaryStore();
  const { load, loading, error, fileCount, loadedFileCount, errors } = dictionary;
  const terms = useMemo(() => dictionary.workspaceId === workspaceId ? dictionary.terms : [], [dictionary.workspaceId, dictionary.terms, workspaceId]);
  const iconSubjects = useMemo(() => new Map(terms.map(term => [`${term.type}:${term.id}`, term])), [terms]);
  const [query, setQuery] = useState('');
  const routeQuery = searchParams?.toString() || '';
  const systemMode = searchParams?.get('view') === 'system';
  const systemScope = [systemMode, searchParams?.get('system'), searchParams?.get('subsystem'), searchParams?.get('process')].join(':');
  useEffect(() => { setQuery(''); }, [systemScope]);
  const latestQuery = useRef(routeQuery);
  useEffect(() => { latestQuery.current = routeQuery; }, [routeQuery]);
  const selectedFiles = useMemo(() => dictionaryFiles(routeQuery), [routeQuery]);
  const fileTerms = useMemo(() => filterTermsByFiles(terms, selectedFiles), [terms, selectedFiles]);
  function updateFiles(path?: string) {
    const selected = dictionaryFiles(latestQuery.current);
    const nextPaths = !path ? [] : selected.includes(path) ? selected.filter(value => value !== path) : [...selected, path];
    const next = dictionaryFilesRoute(latestQuery.current, nextPaths);
    latestQuery.current = next.toString();
    router.replace(`?${next}`, {scroll: false});
  }
  const [preferredLayout, setLayout] = useState<'alphabetical' | 'hierarchy' | 'buckets'>(systemMode ? 'buckets' : 'alphabetical');
  const layout = !systemMode && preferredLayout === 'buckets' ? 'alphabetical' : preferredLayout;
  const bucketsView = layout === 'buckets';
  const kind = dictionaryFilter(searchParams?.toString() || '');
  const [closed, setClosed] = useState<Set<string>>(new Set());
  useEffect(() => { setClosed(new Set()); }, [query]);
  function toggleNode(id: string) {
    setClosed(previous => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }

  useEffect(() => {
    if (workspaceId) void load(workspaceId, refresh);
    setClosed(new Set());
  }, [workspaceId, refresh, load]);

  const scopedTerms = useMemo(() => fileTerms.filter(term => kind === 'all' || term.type === kind), [fileTerms, kind]);
  const matches = useMemo(() => scopedTerms.filter(term => `${term.name} ${term.description || ''}`.toLowerCase().includes(query.trim().toLowerCase())), [scopedTerms, query]);
  const tree = useMemo(() => filterDictionaryTree(buildDictionaryTree(scopedTerms), query), [scopedTerms, query]);

  function selectTerm(term: DictionaryTerm) {
    const params = termRoute(searchParams?.toString() || '', term);
    params.set('browser', 'dictionary');
    if (['network', 'system'].includes(searchParams?.get('view') || '')) params.set('view', 'network');
    router.push(getWorkspacePath(workspaceId, `/ontology?${params}`), { scroll: false });
  }

  function renderTerm(term: DictionaryTerm, itemKey = `${term.type}:${term.id}`) {
    const selected = searchParams?.get('term') === term.id && searchParams?.get('termType') === term.type;
    return <button type="button" data-ontology-tree-item={itemKey} data-ontology-tree-select onClick={() => selectTerm(term)} aria-current={selected ? 'page' : undefined}
      title={`${term.name}\n${term.id}`}
      className={cn('flex min-w-0 flex-1 items-center rounded-md min-h-7 px-2 py-1 text-left text-xs leading-[18px] hover:bg-workspace-accent-10', selected && 'bg-workspace-accent-10 text-workspace-accent')}>
      <OntologyTopicIcon subject={term} className="ontology-sidebar-topic-icon" />
      <span className="min-w-0 truncate">{term.name}</span>
      <span className="sr-only">{dictionaryKindLabel(term.type)}</span>
    </button>;
  }

  function renderNode(node: DictionaryNode, depth = 0, path: string[] = []) {
    const itemPath = [...path, node.id];
    const open = !closed.has(node.id);
    return <li key={node.id} data-ontology-tree-row>
      <div className="flex items-center" style={{ paddingLeft: Math.min(depth, 6) * 12 }}>
        {node.children.length > 0 ? <button type="button" data-ontology-tree-toggle aria-label={`${open ? 'Collapse' : 'Expand'} ${node.name}`} aria-expanded={open}
          onClick={() => toggleNode(node.id)}
          className="shrink-0 rounded p-1 hover:bg-workspace-accent-10"><ChevronRight size={12} className={cn(open && 'rotate-90')} /></button>
          : <span className="w-5 shrink-0" />}
        {node.term ? renderTerm(node.term, JSON.stringify(itemPath)) : <button type="button" data-ontology-tree-item={JSON.stringify(itemPath)} onClick={() => toggleNode(node.id)} className="flex min-w-0 flex-1 items-center px-2 py-1 text-xs leading-[18px] text-muted-foreground" title="Parent declared outside this selection"><OntologyTopicIcon subject={iconSubjects.get(node.id) || { name: node.name }} className="ontology-sidebar-topic-icon" /><span className="min-w-0 truncate">{node.name}</span><span className="ml-1 shrink-0 text-xs">(parent)</span></button>}
      </div>
      {open && node.children.length > 0 && <ul>{node.children.map(child => renderNode(child, depth + 1, itemPath))}</ul>}
    </li>;
  }

  return <div className="space-y-2 px-2 pb-3">
    <label className="relative block"><Search size={13} className="absolute left-2 top-2.5 text-muted-foreground" />
      <input aria-label={bucketsView ? 'Search system elements' : 'Search terms and definitions'} placeholder={bucketsView ? 'Search system elements…' : 'Search terms and definitions…'} value={query} onChange={event => setQuery(event.target.value)}
        className="w-full rounded-md border bg-background py-2 pl-7 pr-2 text-xs" /></label>
    <OntologyFilePicker key={workspaceId} files={files} value={selectedFiles} onToggle={updateFiles} onClear={() => updateFiles()} loading={filesLoading} error={filesError} />
    <div className="flex flex-wrap gap-1" aria-label="Sidebar view">
      {(['alphabetical', 'hierarchy', ...(systemMode ? ['buckets' as const] : [])] as const).map(value => <button key={value} type="button" aria-pressed={layout === value} onClick={() => { setLayout(value); if (bucketsView !== (value === 'buckets')) setQuery(''); }}
        className={cn('rounded-md px-2 py-1 text-xs', layout === value ? 'bg-workspace-accent-10 text-workspace-accent' : 'text-muted-foreground hover:bg-muted')}>
        {value === 'alphabetical' ? 'A–Z' : value === 'hierarchy' ? 'Hierarchy' : '7 buckets'}</button>)}
      {!bucketsView && <select aria-label="Filter dictionary by term type" value={kind}
        onChange={event => router.push(`?${dictionaryFilterRoute(searchParams?.toString() || '', event.target.value as DictionaryTerm['type'] | 'all')}`, {scroll: false})}
        className="ml-auto min-w-0 max-w-full rounded border bg-background px-2 py-1 text-xs">
        <option value="all">All terms</option>
        {termTabs.map(([view, label]) => <option key={view} value={kindForView(view)}>{label}</option>)}
      </select>}
    </div>
    {loading ? <p role="status" className="text-xs text-muted-foreground">Loading terms…</p>
      : error ? <div role="alert" className="text-xs text-destructive">{error} <button type="button" onClick={() => { if (workspaceId) void load(workspaceId, refresh, true); }} className="underline">Retry</button></div>
      : <>{!bucketsView && <p className="text-xs text-muted-foreground" aria-live="polite">{matches.length} of {fileTerms.length} terms · {loadedFileCount} / {fileCount} workspace files</p>}
        {!bucketsView && matches.length === 0 && <p className="text-xs text-muted-foreground">{selectedFiles.length ? 'No matching terms in the selected files.' : terms.length ? 'No matching terms.' : 'No declared terms in the workspace ontology files.'}</p>}
        {errors.length > 0 && <div role="alert" className="space-y-1 text-xs text-destructive"><p>Incomplete dictionary: {errors.length} files could not be read.</p>{errors.map(source => <p key={source.path}>{source.name}: {source.message}</p>)}<button type="button" className="underline" onClick={() => { if (workspaceId) void load(workspaceId, refresh, true); }}>Retry</button></div>}
        {bucketsView ? <OntologySystemTree key={workspaceId} query={query} /> : <nav {...keyboard} aria-label="Ontology terms">{layout === 'alphabetical' ? <ul>{matches.map(term => <li className="flex" key={`${term.type}:${term.id}`} data-ontology-tree-row>{renderTerm(term)}</li>)}</ul>
          : <ul>{tree.map(node => renderNode(node))}</ul>}</nav>}</>}
  </div>;
}
