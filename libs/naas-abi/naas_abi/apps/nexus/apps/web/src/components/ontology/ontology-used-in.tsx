'use client';

import { useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import { ontologyConnections, termConnections, isProcessTerm, type TermRef } from '@/lib/ontology-context';
import { termRoute } from '@/lib/ontology-navigation';
import './ontology-context.css';

export function OntologyUsedIn({term, terms, basePath}: {term: DictionaryTerm; terms: DictionaryTerm[]; basePath?: string}) {
  const router = useRouter(); const params = useSearchParams();
  const [expanded, setExpanded] = useState(false);
  const connections = useMemo(() => ontologyConnections(terms), [terms]);
  const references = termConnections(term, connections).incoming;
  const processes = references.filter(edge => isProcessTerm(edge.from, terms));
  const others = references.filter(edge => !isProcessTerm(edge.from, terms));
  function open(ref: TermRef) {
    if (!ref.type) return;
    const next = termRoute(basePath ? 'view=classes' : params?.toString() || '', {id: ref.id, type: ref.type});
    next.set('browser', 'dictionary');
    router.push(`${basePath || ""}?${next}`, {scroll: false});
  }
  return <section className="ontology-context-used">
    <h2>Used in <span>{references.length}</span></h2>
    <p className="ontology-context-note">References in ontology definitions.</p>
    {([['Processes', processes], ['Other definitions', others]] as const).map(([label, rows]) => rows.length > 0 && <div key={label} className="ontology-context-usage-group">
      <h3>{label} <span>{rows.length}</span></h3>
      <ul>{(expanded ? rows : rows.slice(0, 5)).map(edge => <li key={edge.key}>
        <button type="button" onClick={() => open(edge.from)}>{edge.from.name}</button>
        <span> {edge.label} </span><span>{edge.to.name}</span>
        {edge.kind === 'restriction' && <small>Class restriction</small>}
      </li>)}</ul>
    </div>)}
    {!references.length && <p className="ontology-context-note">No incoming references found in the loaded ontology declarations.</p>}
    {(processes.length > 5 || others.length > 5) && <button className="ontology-context-link" type="button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show fewer' : 'Show all references'}</button>}
    <p className="ontology-context-note">Question mappings and execution evidence are not connected yet.</p>
  </section>;
}
