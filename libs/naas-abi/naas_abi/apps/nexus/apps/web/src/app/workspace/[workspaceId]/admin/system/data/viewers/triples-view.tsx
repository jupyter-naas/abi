'use client';

/** RDF triples as subject / predicate / object, IRIs compacted with prefixes. */
import { useMemo, useState } from 'react';
import { compactIri, formatCount } from '../data-model';

export type Term =
  | { kind: 'iri'; value: string }
  | { kind: 'literal'; value: string; datatype?: string; lang?: string }
  | { kind: 'blank'; value: string };

/** A term in N-Triples syntax: ``<iri>``, ``"text"@en``, ``"1"^^<xsd:int>``, ``_:b0``. */
export function parseTerm(raw: string): Term {
  const term = raw.trim();
  if (term.startsWith('<') && term.endsWith('>')) return { kind: 'iri', value: term.slice(1, -1) };
  if (term.startsWith('_:')) return { kind: 'blank', value: term };
  const literal = term.match(/^"([\s\S]*)"(?:@([A-Za-z-]+)|\^\^<([^>]+)>)?$/);
  if (literal) {
    const value = literal[1].replace(/\\(["\\nrt])/g, (_, c: string) => ({ n: '\n', r: '\r', t: '\t' })[c] ?? c);
    return { kind: 'literal', value, lang: literal[2], datatype: literal[3] };
  }
  return /^[a-z][a-z0-9+.-]*:/i.test(term) ? { kind: 'iri', value: term } : { kind: 'literal', value: term };
}

function TermView({ term, prefixes }: { term: Term; prefixes: Record<string, string> }) {
  if (term.kind === 'iri') {
    return (
      <span className="rdf-iri" title={term.value}>
        {compactIri(term.value, prefixes)}
      </span>
    );
  }
  if (term.kind === 'blank') return <span className="rdf-blank">{term.value}</span>;
  return (
    <span className="rdf-literal">
      <span className="rdf-literal-value" title={term.value.length > 80 ? term.value : undefined}>
        {term.value}
      </span>
      {term.lang && <span className="rdf-literal-meta">@{term.lang}</span>}
      {term.datatype && <span className="rdf-literal-meta">{compactIri(term.datatype, prefixes)}</span>}
    </span>
  );
}

export function TriplesView({
  triples,
  prefixes = {},
  total,
}: {
  triples: [string, string, string][];
  prefixes?: Record<string, string>;
  total?: number | null;
}) {
  const [filter, setFilter] = useState('');
  const parsed = useMemo(() => triples.map((t) => t.map(parseTerm) as [Term, Term, Term]), [triples]);
  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return parsed;
    return parsed.filter((t) => t.some((term) => term.value.toLowerCase().includes(needle)));
  }, [parsed, filter]);
  return (
    <div className="rdf">
      <div className="rdf-toolbar">
        <input
          className="data-input data-input-sm"
          placeholder="Filter triples"
          aria-label="Filter triples"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="data-muted">
          {total !== null && total !== undefined && total > triples.length
            ? `${formatCount(shown.length)} shown · first ${formatCount(triples.length)} of ${formatCount(total)}`
            : `${formatCount(shown.length)} of ${formatCount(triples.length)}`}
        </span>
      </div>
      <div className="grid-scroll">
        <table className="grid-table rdf-table">
          <thead>
            <tr>
              <th>Subject</th>
              <th>Predicate</th>
              <th>Object</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(([s, p, o], i) => (
              <tr key={i}>
                <td>
                  <TermView term={s} prefixes={prefixes} />
                </td>
                <td>
                  <TermView term={p} prefixes={prefixes} />
                </td>
                <td>
                  <TermView term={o} prefixes={prefixes} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
