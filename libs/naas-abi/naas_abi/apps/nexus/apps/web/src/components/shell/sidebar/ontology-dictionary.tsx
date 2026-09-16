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
import { OntologySystemTree } from '@/components/ontology/ontology-system-tree';

export function OntologyDictionary({files, filesLoading, filesError}: {
  files: DictionaryFile[]; filesLoading: boolean; filesError: string | null;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const refresh = useOntologyStore(state => state.graphRefreshTrigger);
  const dictionary = useOntologyDictionaryStore();
  const { load, loading, error, fileCount, loadedFileCount, errors } = dictionary;
  const terms = useMemo(() => dictionary.workspaceId === workspaceId ? dictionary.terms : [], [dictionary.workspaceId, dictionary.terms, workspaceId]);
  const [query, setQuery] = useState('');
  const [fileQuery, setFileQuery] = useState('');
  const routeQuery = searchParams?.toString() || '';
  const systemMode = searchParams?.get('view') === 'system';
  const systemScope = [systemMode, searchParams?.get('system'), searchParams?.get('subsystem'), searchParams?.get('process')].join(':');
  useEffect(() => { setQuery(''); }, [systemScope]);
  const latestQuery = useRef(routeQuery);
  useEffect(() => { latestQuery.current = routeQuery; }, [routeQuery]);
  const selectedFiles = useMemo(() => dictionaryFiles(routeQuery), [routeQuery]);
  const fileTerms = useMemo(() => filterTermsByFiles(terms, selectedFiles), [terms, selectedFiles]);
  const visibleFiles = files.filter(file => `${file.path.split('/').pop()} ${file.name} ${file.moduleName}`.toLowerCase().includes(fileQuery.trim().toLowerCase()));
  const unavailableCount = selectedFiles.filter(path => !files.some(file => file.path === path)).length;
  function updateFiles(path?: string, checked?: boolean) {
    const selected = dictionaryFiles(latestQuery.current);
    const nextPaths = !path ? [] : checked ? [...selected, path] : selected.filter(value => value !== path);
    const next = dictionaryFilesRoute(latestQuery.current, nextPaths);
    latestQuery.current = next.toString();
    router.replace(`?${next}`, {scroll: false});
  }
  const [preferredLayout, setLayout] = useState<'alphabetical' | 'hierarchy' | 'buckets'>(systemMode ? 'buckets' : 'alphabetical');
  const layout = !systemMode && preferredLayout === 'buckets' ? 'alphabetical' : preferredLayout;
  const bucketsView = layout === 'buckets';
  const kind = dictionaryFilter(searchParams?.toString() || '');
  const [closed, setClosed] = useState<Set<string>>(new Set());

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
    router.push(getWorkspacePath(workspaceId, `/ontology?${params}`));
  }

  function renderTerm(term: DictionaryTerm) {
    const selected = searchParams?.get('term') === term.id && searchParams?.get('termType') === term.type;
    return <button type="button" onClick={() => selectTerm(term)} aria-current={selected ? 'page' : undefined}
      title={`${term.name}\n${term.id}`}
      className={cn('flex min-w-0 flex-1 items-center rounded-md min-h-7 px-2 py-1 text-left text-[13px] leading-5 hover:bg-workspace-accent-10', selected && 'bg-workspace-accent-10 text-workspace-accent')}>
      <span className="truncate">{term.name}</span>
      <span className="sr-only">{dictionaryKindLabel(term.type)}</span>
    </button>;
  }

  function renderNode(node: DictionaryNode, depth = 0) {
    const open = !closed.has(node.id) || Boolean(query.trim());
    return <li key={node.id}>
      <div className="flex items-center" style={{ paddingLeft: Math.min(depth, 6) * 12 }}>
        {node.children.length > 0 ? <button type="button" aria-label={`${open ? 'Collapse' : 'Expand'} ${node.name}`} aria-expanded={open}
          onClick={() => setClosed(prev => { const next = new Set(prev); if (next.has(node.id)) next.delete(node.id); else next.add(node.id); return next; })}
          className="shrink-0 rounded p-1 hover:bg-workspace-accent-10"><ChevronRight size={12} className={cn(open && 'rotate-90')} /></button>
          : <span className="w-5 shrink-0" />}
        {node.term ? renderTerm(node.term) : <span className="min-w-0 truncate px-2 py-1 text-[13px] leading-5 text-muted-foreground" title="Parent declared outside this selection">{node.name}<span className="ml-1 text-xs">(parent)</span></span>}
      </div>
      {open && node.children.length > 0 && <ul>{node.children.map(child => renderNode(child, depth + 1))}</ul>}
    </li>;
  }

  return <div className="space-y-2 px-2 pb-3">
    <label className="relative block"><Search size={13} className="absolute left-2 top-2.5 text-muted-foreground" />
      <input aria-label={bucketsView ? 'Search system elements' : 'Search terms and definitions'} placeholder={bucketsView ? 'Search system elements…' : 'Search terms and definitions…'} value={query} onChange={event => setQuery(event.target.value)}
        className="w-full rounded-md border bg-background py-2 pl-7 pr-2 text-xs" /></label>
    <div className="flex flex-wrap gap-1" aria-label="Sidebar view">
      {(['alphabetical', 'hierarchy', ...(systemMode ? ['buckets' as const] : [])] as const).map(value => <button key={value} type="button" aria-pressed={layout === value} onClick={() => { setLayout(value); if (bucketsView !== (value === 'buckets')) setQuery(''); }}
        className={cn('rounded-md px-2 py-1 text-xs', layout === value ? 'bg-workspace-accent-10 text-workspace-accent' : 'text-muted-foreground hover:bg-muted')}>
        {value === 'alphabetical' ? 'A–Z' : value === 'hierarchy' ? 'Hierarchy' : 'BFO buckets'}</button>)}
      {!bucketsView && <select aria-label="Filter dictionary by term type" value={kind}
        onChange={event => router.push(`?${dictionaryFilterRoute(searchParams?.toString() || '', event.target.value as DictionaryTerm['type'] | 'all')}`, {scroll: false})}
        className="ml-auto min-w-0 max-w-full rounded border bg-background px-2 py-1 text-xs">
        <option value="all">All terms</option>
        {termTabs.map(([view, label]) => <option key={view} value={kindForView(view)}>{label}</option>)}
      </select>}
    </div>
    <details className="group/dictionary-files">
      <summary className="flex cursor-pointer list-none items-center gap-1 rounded px-2 py-1 text-xs hover:bg-muted [&::-webkit-details-marker]:hidden">
        <ChevronRight size={12} className="group-open/dictionary-files:rotate-90" />
        <span>Files</span><span className="ml-auto text-muted-foreground">{selectedFiles.length ? `${selectedFiles.length} selected` : 'All files'}</span>
      </summary>
      <div className="mt-1 space-y-2 rounded border p-2">
        <div className="flex items-center justify-between gap-2 text-xs"><span className="text-muted-foreground">Combine files</span>
          {selectedFiles.length > 0 && <button type="button" onClick={() => updateFiles()} className="text-workspace-accent hover:underline">Clear</button>}
        </div>
        <input aria-label="Search ontology files" placeholder="Search files…" value={fileQuery} onChange={event => setFileQuery(event.target.value)} className="w-full rounded border bg-background px-2 py-1.5 text-xs" />
        {filesLoading ? <p role="status" className="text-xs text-muted-foreground">Loading files…</p>
          : filesError ? <p role="alert" className="text-xs text-destructive">{filesError}</p>
          : <div className="max-h-56 overflow-y-auto" role="group" aria-label="Filter by ontology files">
            {visibleFiles.map(file => <label key={file.path} title={`${file.moduleName} · ${file.name}\n${file.path}`} className="flex cursor-pointer items-start gap-2 rounded px-1 py-1.5 hover:bg-muted">
              <input type="checkbox" checked={selectedFiles.includes(file.path)} onChange={event => updateFiles(file.path, event.target.checked)} className="mt-0.5 shrink-0 accent-[var(--workspace-accent)]" />
              <span className="min-w-0"><span className="block truncate font-mono text-xs">{file.path.split('/').pop()}</span><span className="block truncate text-[11px] text-muted-foreground">{file.moduleName}</span></span>
            </label>)}
            {!visibleFiles.length && <p className="py-2 text-xs text-muted-foreground">No matching files.</p>}
          </div>}
        {!filesLoading && !filesError && unavailableCount > 0 && <p role="status" className="text-xs text-muted-foreground">{unavailableCount} selected {unavailableCount === 1 ? 'file is' : 'files are'} no longer available. Clear to reset.</p>}
      </div>
    </details>
    {loading ? <p role="status" className="text-xs text-muted-foreground">Loading terms…</p>
      : error ? <div role="alert" className="text-xs text-destructive">{error} <button type="button" onClick={() => { if (workspaceId) void load(workspaceId, refresh, true); }} className="underline">Retry</button></div>
      : <>{!bucketsView && <p className="text-xs text-muted-foreground" aria-live="polite">{matches.length} of {fileTerms.length} terms · {loadedFileCount} / {fileCount} workspace files</p>}
        {!bucketsView && matches.length === 0 && <p className="text-xs text-muted-foreground">{selectedFiles.length ? 'No matching terms in the selected files.' : terms.length ? 'No matching terms.' : 'No declared terms in the workspace ontology files.'}</p>}
        {errors.length > 0 && <div role="alert" className="space-y-1 text-xs text-destructive"><p>Incomplete dictionary: {errors.length} files could not be read.</p>{errors.map(source => <p key={source.path}>{source.name}: {source.message}</p>)}<button type="button" className="underline" onClick={() => { if (workspaceId) void load(workspaceId, refresh, true); }}>Retry</button></div>}
        {bucketsView ? <OntologySystemTree key={routeQuery} query={query} /> : <nav aria-label="Ontology terms">{layout === 'alphabetical' ? <ul>{matches.map(term => <li className="flex" key={`${term.type}:${term.id}`}>{renderTerm(term)}</li>)}</ul>
          : <ul>{tree.map(node => renderNode(node))}</ul>}</nav>}</>}
  </div>;
}
