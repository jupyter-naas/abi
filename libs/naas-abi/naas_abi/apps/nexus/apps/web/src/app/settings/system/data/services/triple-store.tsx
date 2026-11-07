'use client';

import './triple-store.css';

import { BookOpen, Network, Shapes, Waypoints } from 'lucide-react';
import { compactIri, formatCount } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, CopyButton } from '../data-ui';
import { TriplesView } from '../viewers/triples-view';
import type { ServiceView } from './types';

const SCHEMA_ROLE = 'schema';
// Mirrors the adapter: an absolute IRI safe inside SPARQL's <...>.
const IRI = /^[A-Za-z][A-Za-z0-9+.-]*:[^\s<>"{}|\\^`]+$/;

/** The part of a graph IRI that tells graphs apart, and the rest (without the scheme). */
export function graphParts(iri: string): { base: string; tail: string } {
  const body = iri.replace(/^[a-z][a-z0-9+.-]*:\/\//i, '');
  const trimmed = body.replace(/[/#]+$/, '');
  const cut = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('#'));
  if (cut < 0) return { base: '', tail: trimmed };
  return { base: trimmed.slice(0, cut + 1), tail: trimmed.slice(cut + 1) };
}

/** A log-scale width (0–100) so 10 and 10 million triples both read at a glance. */
export function magnitude(count: number): number {
  if (count <= 0) return 0;
  return Math.min(100, Math.max(4, (Math.log10(count + 1) / 7) * 100));
}

function count(entry: ResourceEntry): number | null {
  const raw = entry.attributes.triples;
  return raw === undefined ? null : Number(raw);
}

function TripleMeter({ entry }: { entry: ResourceEntry }) {
  const n = count(entry);
  if (n === null) return <span className="data-muted">—</span>;
  return (
    <span className="data-triple-store-meter" title={`${formatCount(n)} triples`}>
      <span className="data-triple-store-meter-track" aria-hidden="true">
        <span className="data-triple-store-meter-fill" style={{ width: `${magnitude(n)}%` }} />
      </span>
      <span className="data-num">{formatCount(n)}</span>
    </span>
  );
}

interface GraphSummary {
  triples: [string, string, string][];
  prefixes?: Record<string, string>;
  total?: number | null;
  predicates?: [string, number][];
  classes?: [string, number][];
  predicate_count?: number;
  class_count?: number;
}

function summary(detail: ResourceDetail): GraphSummary | null {
  const view = detail.view as (GraphSummary & { type: string }) | null | undefined;
  return view && view.type === 'triples' ? view : null;
}

function Ranked({
  title,
  icon: Icon,
  items,
  of,
  prefixes,
}: {
  title: string;
  icon: typeof Shapes;
  items: [string, number][];
  of: number | undefined;
  prefixes: Record<string, string>;
}) {
  if (!items.length) return null;
  const top = items[0][1] || 1;
  return (
    <section className="data-triple-store-ranked">
      <h4 className="data-section-title">
        <Icon size={12} aria-hidden="true" /> {title}
        {of !== undefined && of > items.length && <span className="data-muted"> · top {items.length} of {formatCount(of)}</span>}
      </h4>
      <ol className="data-triple-store-ranked-list">
        {items.map(([iri, n]) => (
          <li key={iri} className="data-triple-store-ranked-item" title={iri}>
            <span className="data-triple-store-ranked-label">{compactIri(iri, prefixes)}</span>
            <span className="data-num">{formatCount(n)}</span>
            <span className="data-triple-store-ranked-bar" aria-hidden="true">
              <span style={{ width: `${Math.max(3, (n / top) * 100)}%` }} />
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function GraphPreview({ detail }: { detail: ResourceDetail }) {
  const view = summary(detail);
  if (!view) return null;
  const prefixes = view.prefixes ?? {};
  const total = view.total ?? view.triples.length;
  const sparql = `SELECT ?s ?p ?o WHERE {\n  GRAPH <${detail.entry.id}> { ?s ?p ?o }\n} LIMIT 100`;
  return (
    <div className="data-triple-store-preview">
      <dl className="data-triple-store-stats">
        <div>
          <dt>Triples</dt>
          <dd>{formatCount(total)}</dd>
        </div>
        {view.predicate_count !== undefined && (
          <div>
            <dt>Predicates</dt>
            <dd>{formatCount(view.predicate_count)}</dd>
          </div>
        )}
        {view.class_count !== undefined && (
          <div>
            <dt>Classes</dt>
            <dd>{formatCount(view.class_count)}</dd>
          </div>
        )}
        <div>
          <dt>Prefixes</dt>
          <dd>{Object.keys(prefixes).length}</dd>
        </div>
      </dl>
      {total === 0 ? (
        <p className="data-muted">This graph is empty. Edit it to add triples in Turtle.</p>
      ) : (
        <>
          <div className="data-triple-store-rankings">
            <Ranked title="Classes" icon={Shapes} items={view.classes ?? []} of={view.class_count} prefixes={prefixes} />
            <Ranked
              title="Predicates"
              icon={Waypoints}
              items={view.predicates ?? []}
              of={view.predicate_count}
              prefixes={prefixes}
            />
          </div>
          <TriplesView triples={view.triples} prefixes={prefixes} total={view.total} />
        </>
      )}
      <div className="data-triple-store-query">
        <span className="data-muted">Query it with SPARQL</span>
        <code className="data-mono">{`GRAPH <${detail.entry.id}>`}</code>
        <CopyButton value={sparql} label="Copy a SPARQL query" />
      </div>
    </div>
  );
}

const TEMPLATE = `@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <http://example.org/> .

ex:thing a ex:Thing ;
    rdfs:label "A thing"@en ;
    ex:createdOn "2026-10-02"^^xsd:date .
`;

export const tripleStoreView: ServiceView = {
  name: 'triple_store',
  label: 'Knowledge graph',
  description: 'Named RDF graphs: ontologies, schema and instance data.',
  icon: Network,
  group: 'Storage',
  noun: { one: 'graph', many: 'graphs' },
  nounFor: () => ({ one: 'graph', many: 'graphs' }),
  entryIcon: (entry) => (entry.attributes.role === SCHEMA_ROLE ? BookOpen : Network),
  summary: (entry) => {
    const { base } = graphParts(entry.id);
    return base ? <span className="data-triple-store-iri">{base}</span> : null;
  },
  badges: (entry) => (
    <>
      {entry.attributes.role === SCHEMA_ROLE && <Badge tone="info">Schema · read-only</Badge>}
      {count(entry) === 0 && <Badge>Empty</Badge>}
    </>
  ),
  level: () => ({
    columns: [{ id: 'triples', label: 'Triples', width: '168px', align: 'end', render: (e) => <TripleMeter entry={e} /> }],
    emptyTitle: 'No named graphs',
    emptyText: 'Create one from Turtle, or let a module load its ontologies.',
  }),
  facts: (detail) => {
    const view = summary(detail);
    const facts: { label: string; value: React.ReactNode }[] = [];
    const total = view?.total ?? count(detail.entry);
    if (total !== null && total !== undefined) facts.push({ label: 'Triples', value: formatCount(total) });
    if (view?.predicate_count !== undefined) facts.push({ label: 'Predicates', value: formatCount(view.predicate_count) });
    if (view?.class_count !== undefined) facts.push({ label: 'Classes', value: formatCount(view.class_count) });
    return facts;
  },
  preview: (detail) => (summary(detail) ? <GraphPreview detail={detail} /> : null),
  createLabel: 'New graph',
  inspectorWidth: 620,
  editor: {
    language: () => 'turtle',
    template: () => TEMPLATE,
    namePlaceholder: 'http://ontology.naas.ai/graph/my-graph',
    validateName: (name) =>
      IRI.test(name.trim())
        ? null
        : 'A graph name is an absolute IRI, e.g. http://ontology.naas.ai/graph/my-graph (no spaces, <, >, quotes or braces).',
  },
  deleteWarning: (entry) =>
    `Drops the graph and every triple in it${
      count(entry) ? ` (${formatCount(count(entry) ?? 0)})` : ''
    }. Anything querying it, agents included, sees nothing afterwards.`,
};
