'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import { OntologyDictionaryEntry } from '@/components/shell/sidebar/ontology-dictionary-entry';
import { ImageSquare } from '@/components/image-square';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useOntologyStore } from '@/stores/ontology';
import { classDefinitionHref } from '@/lib/graph-instance-browser';
import type { ExplorerClass } from '@/lib/graph-explorer';

export function ExplorerClassDetails({ workspaceId, classUri, classInfo }: {
  workspaceId: string;
  classUri: string;
  classInfo?: ExplorerClass;
}) {
  const dictionary = useOntologyDictionaryStore();
  const { load } = dictionary;
  const revision = useOntologyStore(state => state.graphRefreshTrigger);
  useEffect(() => { void load(workspaceId, revision); }, [workspaceId, revision, load]);
  const term = dictionary.workspaceId === workspaceId
    ? dictionary.terms.find(item => item.id === classUri && item.type === 'entity') : undefined;
  return <div className="graph-explorer-class-details">
    <div className="graph-explorer-details-context">
      <span>{classInfo ? `${classInfo.count.toLocaleString()} instances in the selected graphs` : 'Class definition'}</span>
      {term && <Link href={classDefinitionHref(workspaceId, classUri)}>Open in Ontology <ArrowUpRight size={13} /></Link>}
    </div>
    {dictionary.loading || dictionary.workspaceId !== workspaceId ? (
      <p className="graph-explorer-message" role="status">Loading class definition…</p>
    ) : dictionary.error ? (
      <p className="graph-explorer-message" role="alert">{dictionary.error}<button onClick={() => void load(workspaceId, revision, true)}>Retry</button></p>
    ) : term ? (
      <OntologyDictionaryEntry context={{ workspaceId, termId: classUri, basePath: `/workspace/${encodeURIComponent(workspaceId)}/ontology` }} />
    ) : (
      <section className="graph-explorer-missing-definition">
        <ImageSquare
          fallback={<OntologyTopicIcon subject={{ id: classUri, name: classInfo?.label || classUri, type: 'entity' }} />}
        />
        <h1>{classInfo?.label || classUri}</h1>
        <p>This class is used in the selected graphs, but its definition is not available in the workspace ontology files.</p>
        <dl><dt>Class URI</dt><dd>{classUri}</dd></dl>
        {Boolean(dictionary.errors.length) && <p>Some ontology files could not be loaded. <button onClick={() => void load(workspaceId, revision, true)}>Retry</button></p>}
      </section>
    )}
  </div>;
}
