'use client';

import { useOntologyIcon } from '@/hooks/use-ontology-icon';
import type { OntologyTopicSubject } from '@/lib/ontology-topic-icon';
import './ontology-topic-icon.css';

/** Saved workspace choice, with the topic glyph as a fallback while artwork loads. */
export function OntologyTopicIcon({ subject, className = '' }: { subject: OntologyTopicSubject; className?: string }) {
  const { name, paths } = useOntologyIcon(subject);
  return <svg className={`ontology-topic-icon ${className}`} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" data-topic-icon={`material-symbols-light:${name}`}>
    {paths.map((path, index) => <path key={index} d={path} />)}
  </svg>;
}
