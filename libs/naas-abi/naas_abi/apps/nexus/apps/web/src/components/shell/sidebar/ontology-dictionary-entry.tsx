'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useWorkspaceStore } from '@/stores/workspace';
import { OntologyIconPicker } from '@/components/ontology/ontology-icon-picker';
import '@/components/ontology/ontology-detail.css';
import { OntologyUsedIn } from '@/components/ontology/ontology-used-in';
import { classProperties } from '@/lib/ontology-class-properties';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { ontologyBrowser, termRoute } from '@/lib/ontology-navigation';
import { dictionaryKindLabel } from '@/lib/ontology-dictionary-tree';
import { BookOpen, FileCode } from 'lucide-react';

export function OntologyDictionaryEntry() {
  const router = useRouter();
  const params = useSearchParams();
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const { terms, loading, error, workspaceId: loadedWorkspace, errors } = useOntologyDictionaryStore();
  const scope = ontologyBrowser(params?.toString() || '') === 'dictionary' ? null : params?.get('ontology');
  const term = loadedWorkspace === workspaceId ? terms.find(item => item.id === params?.get('term') && item.type === params?.get('termType') && (!scope || item.sources?.some(source => source.path === scope))) : undefined;
  const linkedTerm = (id: string, name: string, kind?: DictionaryTerm['type']) => {
    const target = terms.find(item => item.id === id && (!kind || item.type === kind));
    if (!target) return <span title={id}>{name}</span>;
    return <button type="button" className="text-workspace-accent hover:underline" onClick={() => {
      const next = termRoute(params?.toString() || '', target);
      if (scope && !target.sources?.some(source => source.path === scope)) next.set('browser', 'dictionary');
      router.push(`?${next}`);
    }}>{name}</button>;
  };
  if (loading || loadedWorkspace !== workspaceId) return <p className="p-6 text-sm text-muted-foreground" role="status">Loading the workspace dictionary…</p>;
  if (error) return <p className="p-6 text-sm text-destructive" role="alert">{error}</p>;
  if (!term) return <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
    <BookOpen size={28} className="text-workspace-accent" /><h2 className="text-lg font-semibold">Select a term</h2>
    <p className="max-w-md text-sm text-muted-foreground">{params?.get('term') ? 'This term is not available in the current selection.' : 'Select a term from the sidebar to read its definition and see where it is defined.'}</p>
    {errors.length > 0 && <p className="text-sm text-destructive">Some ontology files could not be read. See the sidebar for details.</p>}
  </div>;
  const properties = classProperties(term, terms);
  const missing = <span className="text-muted-foreground">Not specified</span>;
  const parentLabel = term.type === 'entity' ? 'Subclass of' : term.type === 'individual' ? 'Instance of' : 'Subproperty of';
  const renderLinks = (links: Array<{id: string; name: string}> | undefined, kind?: DictionaryTerm['type']) => links?.length
    ? <div className="flex flex-wrap gap-x-3 gap-y-1">{links.map(link => <span key={link.id}>{linkedTerm(link.id, link.name, kind)}</span>)}</div> : missing;
  const renderValues = (values?: string[]) => values?.length ? values.map(value => <p key={value}>{value}</p>) : missing;
  return <article className="min-w-0 flex-1 overflow-y-auto p-4 md:p-5">
    <OntologyIconPicker subject={term} className="ontology-detail-topic-icon" />
    <h1 className="break-words text-xl font-semibold">{term.name}</h1>
    <p className="mt-1 text-xs text-muted-foreground">{dictionaryKindLabel(term.type)}</p>
    <dl className="mt-5 divide-y rounded-md border text-sm">
      <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">URIRef</dt><dd className="break-all font-mono text-xs leading-6">{term.id}</dd></div>
      <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">{parentLabel}</dt><dd className="leading-6">{renderLinks(term.parents, term.type === 'individual' ? 'entity' : term.type)}</dd></div>
      <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">Definition</dt><dd className="leading-6">
        {term.description || missing}
        {new Set(term.definitions?.map(def => def.value)).size > 1 && <details className="mt-2"><summary className="cursor-pointer text-xs text-muted-foreground">Definitions across source files</summary>
          <ul className="mt-2 space-y-3">{term.definitions?.map((def, i) => <li key={i}><p>{def.value}</p><p className="text-xs text-muted-foreground">{def.source_path.split('/').pop()}</p></li>)}</ul></details>}
      </dd></div>
      <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">Examples</dt><dd className="space-y-2 leading-6">{renderValues(term.examples)}</dd></div>
      <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">Aliases</dt><dd className="leading-6">{renderValues(term.aliases)}</dd></div>
      <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">Point of contact</dt><dd className="leading-6">{renderValues(term.contacts)}</dd></div>
      <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">Contributors</dt><dd className="leading-6">{renderValues(term.contributors)}</dd></div>
      {([['Domain', term.domain], ['Range', term.range], ['Inverse', term.inverse]] as const).map(([label, links]) => links?.length ?
        <div key={label} className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">{label}</dt><dd className="leading-6">{renderLinks(links, label === 'Inverse' ? 'relationship' : undefined)}</dd></div> : null)}
    </dl>
    {term.type === 'entity' && <section className="mt-4 overflow-hidden rounded-md border">
      <h2 className="border-b px-4 py-2.5 text-sm font-medium">Properties <span className="ml-2 text-xs text-muted-foreground">{properties.length}</span></h2>
      {properties.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground"><tr><th className="px-4 py-2 font-normal">Property</th><th className="px-4 py-2 font-normal">Type</th><th className="px-4 py-2 font-normal">Range</th><th className="px-4 py-2 font-normal">Declared on</th></tr></thead>
        <tbody>{properties.map(({property, declaredOn}) => <tr key={`${property.type}:${property.id}`} className="border-t align-top">
          <td className="px-4 py-2">{linkedTerm(property.id, property.name, property.type)}</td>
          <td className="px-4 py-2 text-xs leading-5 text-muted-foreground">{dictionaryKindLabel(property.type)}</td>
          <td className="px-4 py-2">{renderLinks(property.range)}</td>
          <td className="px-4 py-2">{renderLinks(declaredOn, 'entity')}</td>
        </tr>)}</tbody>
      </table><p className="border-t px-4 py-2 text-xs text-muted-foreground">Properties with a declared domain on this class or its parents.</p></div>
        : <p className="px-4 py-4 text-sm text-muted-foreground">No properties with a named domain on this class or its parents.</p>}
      {!!errors.length && <p role="status" className="border-t px-4 py-2 text-xs text-muted-foreground">Some workspace files could not be read. Properties may be incomplete.</p>}
    </section>}
    <OntologyUsedIn key={`${term.type}:${term.id}`} term={term} terms={terms} />
    <section className="mt-6"><h2 className="text-sm font-semibold">Defined in {term.sources?.length} source {term.sources?.length === 1 ? 'file' : 'files'}</h2>
      <ul className="mt-3 space-y-2">{term.sources?.map(source => <li key={source.path}><button type="button" title={source.path} className="flex max-w-full items-start gap-2 text-left text-sm text-workspace-accent hover:underline" onClick={() => {
        const next = new URLSearchParams({ browser: 'files', view: params?.get('view') || 'classes', ontology: source.path, term: term.id, termType: term.type });
        router.push(`?${next}`);
      }}><FileCode size={16} className="mt-0.5 shrink-0 text-workspace-accent" /><span className="min-w-0"><span className="block break-words">{source.path.split('/').pop()}</span><span className="text-xs text-muted-foreground">{source.moduleName} · {source.name}</span></span></button></li>)}</ul>
    </section>
  </article>;
}
