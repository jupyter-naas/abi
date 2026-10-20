'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useOntologyIconsStore } from '@/stores/ontology-icons';
import { useWorkspaceStore } from '@/stores/workspace';
import { ImageSquare } from '@/components/image-square';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { isMaterialIconValue, uploadObjectImage } from '@/lib/image-square';
import { instanceImageValue } from '@/lib/instance-image';
import { iconTarget, iconTargetKey } from '@/lib/ontology-icon-library';
import '@/components/ontology/ontology-detail.css';
import { OntologyUsedIn } from '@/components/ontology/ontology-used-in';
import { classProperties, classRestrictions } from '@/lib/ontology-class-properties';
import { referencedClasses } from '@/lib/ontology-bfo-groups';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { ontologyBrowser, termRoute } from '@/lib/ontology-navigation';
import { dictionaryKindLabel } from '@/lib/ontology-dictionary-tree';
import { BookOpen, FileCode, RefreshCw } from 'lucide-react';
import { BFO_BUCKET_BY_TYPE, BFO_BUCKET_BY_URI } from '@/lib/bfo-buckets';
import { bfoBucketResolver } from '@/lib/detail-network';
import { cn } from '@/lib/utils';

export function OntologyDictionaryEntry({ context }: { context?: { workspaceId: string; termId: string; basePath: string } } = {}) {
  const router = useRouter();
  const routeParams = useSearchParams();
  const currentWorkspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const workspaceId = context?.workspaceId || currentWorkspaceId;
  const icons = useOntologyIconsStore();
  useEffect(() => { if (workspaceId) void icons.load(workspaceId); }, [workspaceId, icons.load]);
  const params = context ? new URLSearchParams({ browser: 'dictionary', view: 'classes', term: context.termId, termType: 'entity' }) : routeParams;
  const { terms, loading, error, workspaceId: loadedWorkspace, errors, refreshBfoBucket } = useOntologyDictionaryStore();
  const resolveBucket = useMemo(() => bfoBucketResolver(terms, { entityFallback: true }), [terms]);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const scope = ontologyBrowser(params?.toString() || '') === 'dictionary' ? null : params?.get('ontology');
  const termId = params?.get('term');
  const termType = params?.get('termType');
  const term = useMemo(() => {
    if (loadedWorkspace !== workspaceId) return undefined;
    const declared = terms.find(item => item.id === termId && item.type === termType && (!scope || item.sources?.some(source => source.path === scope)));
    if (declared || !scope || termType !== 'entity') return declared;
    // A class the file only points at through a restriction (abi:GeospatialRegion in PeopleOntology).
    return referencedClasses(terms.filter(item => item.sources?.some(source => source.path === scope)), terms, [scope]).find(item => item.id === termId);
  }, [loadedWorkspace, workspaceId, terms, termId, termType, scope]);
  const linkedTerm = (id: string, name: string, kind?: DictionaryTerm['type']) => {
    const target = terms.find(item => item.id === id && (!kind || item.type === kind));
    if (!target) return <span title={id}>{name}</span>;
    return <button type="button" className="text-workspace-accent hover:underline" onClick={() => {
      const next = termRoute(params?.toString() || '', target);
      if (scope && !target.sources?.some(source => source.path === scope)) next.set('browser', 'dictionary');
      router.push(`${context?.basePath || ""}?${next}`);
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
  const restrictions = classRestrictions(term, terms);
  const fileName = (path: string) => path.split('/').pop();
  const owlImage = instanceImageValue({
    relations: (term.relations || []).map(relation => ({
      predicate_uri: relation.property.id,
      predicate_label: relation.property.name,
      other_uri: relation.target.id,
    })),
  });
  const target = iconTarget(term);
  const override = target && icons.workspaceId === workspaceId ? icons.icons[iconTargetKey(target)] : undefined;
  const imageValue = !override ? owlImage : isMaterialIconValue(override) ? undefined : override;
  const missing = <span className="text-muted-foreground">Not specified</span>;
  const bucket = BFO_BUCKET_BY_URI[resolveBucket(term.id) || ''] || BFO_BUCKET_BY_TYPE.Unknown;
  const refreshBucket = async () => {
    if (!workspaceId) return;
    setRefreshing(true); setRefreshError(null);
    try { await refreshBfoBucket(workspaceId, term.id); }
    catch (err) { setRefreshError(err instanceof Error ? err.message : 'Could not refresh the BFO bucket.'); }
    finally { setRefreshing(false); }
  };
  const parentLabel = term.type === 'entity' ? 'Subclass of' : term.type === 'individual' ? 'Instance of' : 'Subproperty of';
  const renderLinks = (links: Array<{id: string; name: string}> | undefined, kind?: DictionaryTerm['type']) => links?.length
    ? <div className="flex flex-wrap gap-x-3 gap-y-1">{links.map(link => <span key={link.id}>{linkedTerm(link.id, link.name, kind)}</span>)}</div> : missing;
  const renderValues = (values?: string[]) => values?.length ? values.map(value => <p key={value}>{value}</p>) : missing;
  return <article className="min-w-0 flex-1 overflow-y-auto p-4 md:p-5">
    <ImageSquare
      src={imageValue}
      fallback={<OntologyTopicIcon subject={term} />}
      label={term.name}
      currentIcon={override && isMaterialIconValue(override) ? override : null}
      disabled={!workspaceId || !icons.canEdit}
      disabledReason="Your workspace role cannot change this image"
      onCommit={workspaceId && target ? async (value) => { await icons.save(workspaceId, target, value); } : undefined}
      onUpload={workspaceId ? (file) => uploadObjectImage(workspaceId, file) : undefined}
    />
    <h1 className="break-words text-xl font-semibold">{term.name}</h1>
    <p className="mt-1 break-all font-mono text-xs text-muted-foreground">{term.id}</p>
    <p className="mt-1 text-xs text-muted-foreground">{dictionaryKindLabel(term.type)}</p>
    <dl className="mt-5 divide-y rounded-md border text-sm">
      {term.type === 'entity' && <div className="grid gap-2 px-4 py-2.5 sm:grid-cols-[128px_minmax(0,1fr)]"><dt className="text-xs leading-6 text-muted-foreground">BFO 7 buckets</dt><dd className="flex items-center gap-2 leading-6">
        <span className="h-2.5 w-2.5 shrink-0 rounded-full border" style={{ backgroundColor: bucket.color, borderColor: bucket.border }} />
        <span title={bucket.uri || bucket.description}>{bucket.type === 'Unknown' || bucket.type === 'Entity' ? bucket.type : `${bucket.label} · ${bucket.type}`}</span>
        <button type="button" onClick={() => void refreshBucket()} disabled={refreshing || !workspaceId}
          aria-label="Clear the cached BFO bucket and resolve it again" title="Clear the cached BFO bucket and resolve it again"
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50">
          <RefreshCw size={13} className={cn(refreshing && 'animate-spin')} /></button>
        {refreshError && <span role="alert" className="text-xs text-destructive">{refreshError}</span>}
      </dd></div>}
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
    {term.type === 'entity' && ([['relationship', 'Object Properties'], ['attribute', 'Data Properties']] as const).map(([kind, title]) => {
      const rows = properties.filter(({property}) => property.type === kind);
      return <section key={kind} className="mt-4 overflow-hidden rounded-md border">
        <h2 className="border-b px-4 py-2.5 text-sm font-medium">{title} <span className="ml-2 text-xs text-muted-foreground">{rows.length}</span></h2>
        {rows.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <thead className="text-xs text-muted-foreground"><tr><th className="px-4 py-2 font-normal">Property</th><th className="px-4 py-2 font-normal">Range</th><th className="px-4 py-2 font-normal">Declared on</th></tr></thead>
          <tbody>{rows.map(({property, declaredOn}) => <tr key={property.id} className="border-t align-top">
            <td className="px-4 py-2">{linkedTerm(property.id, property.name, property.type)}</td>
            <td className="px-4 py-2">{renderLinks(property.range)}</td>
            <td className="px-4 py-2">{renderLinks(declaredOn, 'entity')}</td>
          </tr>)}</tbody>
        </table><p className="border-t px-4 py-2 text-xs text-muted-foreground">{title} with a declared domain on this class or its parents.</p></div>
          : <p className="px-4 py-4 text-sm text-muted-foreground">No {title.toLowerCase()} with a named domain on this class or its parents.</p>}
        {!!errors.length && <p role="status" className="border-t px-4 py-2 text-xs text-muted-foreground">Some workspace files could not be read. {title} may be incomplete.</p>}
      </section>;
    })}
    {term.type === 'entity' && <section className="mt-4 overflow-hidden rounded-md border">
      <h2 className="border-b px-4 py-2.5 text-sm font-medium">Restrictions <span className="ml-2 text-xs text-muted-foreground">{restrictions.length}</span></h2>
      {restrictions.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground"><tr><th className="px-4 py-2 font-normal">Property</th><th className="px-4 py-2 font-normal">Constraint</th><th className="px-4 py-2 font-normal">Filler</th><th className="px-4 py-2 font-normal">Declared on</th><th className="px-4 py-2 font-normal">Stated in</th></tr></thead>
        <tbody>{restrictions.map(item => <tr key={item.key} className="border-t align-top">
          <td className="px-4 py-2">{linkedTerm(item.property.id, item.property.name, 'relationship')}</td>
          <td className="px-4 py-2 font-mono text-xs leading-5 text-muted-foreground">{item.constraint || 'some'}</td>
          <td className="px-4 py-2">{linkedTerm(item.target.id, item.target.name)}</td>
          <td className="px-4 py-2">{item.declaredOn.id === term.id ? <span className="text-muted-foreground">This class</span> : linkedTerm(item.declaredOn.id, item.declaredOn.name, 'entity')}</td>
          <td className="px-4 py-2 text-xs leading-5 text-muted-foreground">{item.sources.map(source => <span key={source.path} className="block" title={source.path}>{fileName(source.path)}</span>)}</td>
        </tr>)}</tbody>
      </table><p className="border-t px-4 py-2 text-xs text-muted-foreground">owl:Restriction statements on this class or its parents.</p></div>
        : <p className="px-4 py-4 text-sm text-muted-foreground">No restrictions on this class or its parents.</p>}
    </section>}
    <OntologyUsedIn key={`${term.type}:${term.id}`} term={term} terms={terms} basePath={context?.basePath} />
    <section className="mt-6"><h2 className="text-sm font-semibold">Defined in {term.sources?.length} source {term.sources?.length === 1 ? 'file' : 'files'}</h2>
      <ul className="mt-3 space-y-2">{term.sources?.map(source => <li key={source.path}><button type="button" title={source.path} className="flex max-w-full items-start gap-2 text-left text-sm text-workspace-accent hover:underline" onClick={() => {
        const next = new URLSearchParams({ browser: 'files', view: params?.get('view') || 'classes', ontology: source.path, term: term.id, termType: term.type });
        router.push(`${context?.basePath || ""}?${next}`);
      }}><FileCode size={16} className="mt-0.5 shrink-0 text-workspace-accent" /><span className="min-w-0"><span className="block break-words">{source.path.split('/').pop()}</span><span className="text-xs text-muted-foreground">{source.moduleName} · {source.name}</span></span></button></li>)}</ul>
    </section>
  </article>;
}
