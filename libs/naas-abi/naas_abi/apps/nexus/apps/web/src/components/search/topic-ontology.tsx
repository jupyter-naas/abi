'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import { OntologyDictionaryEntry } from '@/components/shell/sidebar/ontology-dictionary-entry';
import { classDefinitionHref } from '@/lib/graph-instance-browser';
import type { SearchTopic } from '@/lib/search-topics';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useOntologyStore } from '@/stores/ontology';

/**
 * The ontology behind a topic: its class, as the workspace ontology defines it
 * (same entry the Ontology page and the graph explorer show). The topic's
 * queries live in Settings → Search.
 */
export function TopicOntology({ workspaceId, topic }: { workspaceId: string; topic: SearchTopic }) {
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
    </div>
  );
}
