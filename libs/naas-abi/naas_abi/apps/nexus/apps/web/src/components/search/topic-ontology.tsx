'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowUpRight, Settings2 } from 'lucide-react';
import { OntologyDictionaryEntry } from '@/components/shell/sidebar/ontology-dictionary-entry';
import { classDefinitionHref } from '@/lib/graph-instance-browser';
import type { SearchTopic } from '@/lib/search-topics';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useOntologyStore } from '@/stores/ontology';
import { SparqlDisclosure } from './sparql-disclosure';

/**
 * The ontology behind a topic: its class, as the workspace ontology defines it
 * (same entry the Ontology page and the graph explorer show), and the queries
 * the topic runs over it.
 */
export function TopicOntology({ workspaceId, topic, canEdit }: { workspaceId: string; topic: SearchTopic; canEdit: boolean }) {
  const dictionary = useOntologyDictionaryStore();
  const { load } = dictionary;
  const revision = useOntologyStore(state => state.graphRefreshTrigger);
  useEffect(() => { void load(workspaceId, revision); }, [workspaceId, revision, load]);

  const classIri = topic.class_iri;
  const term = classIri && dictionary.workspaceId === workspaceId
    ? dictionary.terms.find(item => item.id === classIri && item.type === 'entity') : undefined;

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>Class searched by <strong className="text-foreground">{topic.plural_label}</strong>{classIri && <> · <span className="font-mono">{classIri}</span></>}</span>
          {term && <Link href={classDefinitionHref(workspaceId, classIri)} className="inline-flex items-center gap-1 text-workspace-accent hover:underline">Open in Ontology <ArrowUpRight size={12} /></Link>}
        </div>
        {!classIri ? (
          <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">This topic names no class. Set one in the search settings to show its definition here.</p>
        ) : dictionary.loading || dictionary.workspaceId !== workspaceId ? (
          <p className="text-sm text-muted-foreground" role="status">Loading class definition…</p>
        ) : dictionary.error ? (
          <p className="text-sm text-red-500" role="alert">{dictionary.error}</p>
        ) : term ? (
          <div className="rounded-lg border bg-card p-3">
            <OntologyDictionaryEntry context={{ workspaceId, termId: classIri, basePath: `/workspace/${encodeURIComponent(workspaceId)}/ontology` }} />
          </div>
        ) : (
          <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
            The class is not defined in the ontologies this workspace loads.
          </p>
        )}
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Queries</h3>
          {canEdit && (
            <Link href={`/workspace/${encodeURIComponent(workspaceId)}/settings/search?topic=${encodeURIComponent(topic.id)}`} className="inline-flex items-center gap-1 text-xs text-workspace-accent hover:underline">
              <Settings2 size={12} /> Edit in settings
            </Link>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Each query runs on the graphs this workspace can read. Its variables fill the result list, the header and the sections.
        </p>
        <div className="space-y-1">
          <QueryRow label="Results" sparql={topic.results_query} />
          <QueryRow label="Header" sparql={topic.header_query} />
          {topic.sections.map(s => <QueryRow key={s.id} label={`Section · ${s.label}`} sparql={s.query} />)}
        </div>
      </section>
    </div>
  );
}

function QueryRow({ label, sparql }: { label: string; sparql: string }) {
  return (
    <div className="rounded-md border px-2 py-1.5">
      <div className="flex items-center justify-between gap-2 text-sm"><span>{label}</span></div>
      <SparqlDisclosure sparql={sparql} label="Show query" />
    </div>
  );
}
