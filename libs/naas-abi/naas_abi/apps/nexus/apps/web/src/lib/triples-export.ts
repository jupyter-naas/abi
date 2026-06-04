/** RDF triple row used by the discovery triples preview table. */
export interface ExportTriple {
  s: string;
  p: string;
  o: string;
  isLiteral: boolean;
}

export type TripleExportFormat = 'nt' | 'ttl' | 'owl';

const WELL_KNOWN_PREFIXES: Record<string, string> = {
  'http://www.w3.org/1999/02/22-rdf-syntax-ns#': 'rdf',
  'http://www.w3.org/2000/01/rdf-schema#': 'rdfs',
  'http://www.w3.org/2002/07/owl#': 'owl',
  'http://www.w3.org/2001/XMLSchema#': 'xsd',
};

function splitUri(uri: string): { namespace: string; local: string } | null {
  const trimmed = uri.trim();
  if (!trimmed) return null;
  const hashIdx = trimmed.lastIndexOf('#');
  if (hashIdx >= 0) {
    return { namespace: trimmed.slice(0, hashIdx + 1), local: trimmed.slice(hashIdx + 1) };
  }
  const slashIdx = trimmed.lastIndexOf('/');
  if (slashIdx >= 0) {
    return { namespace: trimmed.slice(0, slashIdx + 1), local: trimmed.slice(slashIdx + 1) };
  }
  return null;
}

function escapeStringLiteral(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r')
    .replace(/\t/g, '\\t');
}

function isAbsoluteUri(term: string): boolean {
  return /^https?:\/\//i.test(term) || /^urn:/i.test(term);
}

/** Collect namespace → prefix mappings from all URI terms in the triple set. */
export function buildPrefixMap(triples: ExportTriple[]): Map<string, string> {
  const namespaces = new Set<string>();
  for (const t of triples) {
    for (const uri of [t.s, t.p, t.isLiteral ? null : t.o]) {
      if (!uri) continue;
      const split = splitUri(uri);
      if (split) namespaces.add(split.namespace);
    }
  }

  const prefixByNs = new Map<string, string>();
  const usedPrefixes = new Set<string>(Object.values(WELL_KNOWN_PREFIXES));

  for (const ns of [...namespaces].sort()) {
    const known = WELL_KNOWN_PREFIXES[ns];
    if (known) {
      prefixByNs.set(ns, known);
      continue;
    }
    let base =
      ns
        .replace(/^https?:\/\//i, '')
        .replace(/[^a-zA-Z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '')
        .slice(0, 24) || 'ns';
    if (/^\d/.test(base)) base = `ns_${base}`;
    let candidate = base;
    let n = 0;
    while (usedPrefixes.has(candidate)) {
      n += 1;
      candidate = `${base}${n}`;
    }
    usedPrefixes.add(candidate);
    prefixByNs.set(ns, candidate);
  }

  return prefixByNs;
}

function formatUriTerm(uri: string, prefixByNs: Map<string, string>): string {
  const split = splitUri(uri);
  if (!split) return `<${uri}>`;
  const prefix = prefixByNs.get(split.namespace);
  if (!prefix) return `<${uri}>`;
  const local = split.local.replace(/[^a-zA-Z0-9_-]/g, '_');
  if (!local) return `<${uri}>`;
  return `${prefix}:${local}`;
}

function formatObject(o: string, isLiteral: boolean, prefixByNs: Map<string, string>): string {
  if (isLiteral) {
    if (isAbsoluteUri(o)) return formatUriTerm(o, prefixByNs);
    return `"${escapeStringLiteral(o)}"`;
  }
  return formatUriTerm(o, prefixByNs);
}

function dedupeTriples(triples: ExportTriple[]): ExportTriple[] {
  const seen = new Set<string>();
  const out: ExportTriple[] = [];
  for (const t of triples) {
    const key = `${t.s}\0${t.p}\0${t.o}\0${t.isLiteral}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

export function triplesToNTriples(triples: ExportTriple[]): string {
  const rows = dedupeTriples(triples);
  return rows
    .map((t) => {
      const s = `<${t.s}>`;
      const p = `<${t.p}>`;
      const o = t.isLiteral
        ? isAbsoluteUri(t.o)
          ? `<${t.o}>`
          : `"${escapeStringLiteral(t.o)}"`
        : `<${t.o}>`;
      return `${s} ${p} ${o} .`;
    })
    .join('\n');
}

function prefixLines(prefixByNs: Map<string, string>): string[] {
  const inverted = new Map<string, string>();
  for (const [ns, prefix] of prefixByNs) {
    if (!inverted.has(prefix)) inverted.set(prefix, ns);
  }
  return [...inverted.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([prefix, ns]) => `@prefix ${prefix}: <${ns}> .`);
}

/** Group triples by subject URI (same layout rdflib uses for Turtle). */
export function groupTriplesBySubject(triples: ExportTriple[]): Map<string, ExportTriple[]> {
  const map = new Map<string, ExportTriple[]>();
  for (const t of dedupeTriples(triples)) {
    const list = map.get(t.s) ?? [];
    list.push(t);
    map.set(t.s, list);
  }
  return map;
}

export function triplesToTurtle(triples: ExportTriple[], opts?: { ontologyHeader?: boolean }): string {
  const rows = dedupeTriples(triples);
  const prefixByNs = buildPrefixMap(rows);
  const lines = [...prefixLines(prefixByNs), ''];

  if (opts?.ontologyHeader) {
    lines.push('# OWL/RDF serialization of discovery triples preview', '');
  }

  const bySubject = [...groupTriplesBySubject(rows).entries()].sort(([a], [b]) =>
    a.localeCompare(b),
  );

  for (const [subject, preds] of bySubject) {
    const sorted = [...preds].sort((a, b) => a.p.localeCompare(b.p));
    const sTerm = formatUriTerm(subject, prefixByNs);
    sorted.forEach((t, i) => {
      const p = formatUriTerm(t.p, prefixByNs);
      const o = formatObject(t.o, t.isLiteral, prefixByNs);
      const isLast = i === sorted.length - 1;
      const lineEnd = isLast ? ' .' : ' ;';
      if (i === 0) {
        lines.push(`${sTerm} ${p} ${o}${lineEnd}`);
      } else {
        lines.push(`    ${p} ${o}${lineEnd}`);
      }
    });
    lines.push('');
  }

  return `${lines.join('\n')}\n`;
}

export function serializeTriples(triples: ExportTriple[], format: TripleExportFormat): {
  content: string;
  filename: string;
  mime: string;
} {
  switch (format) {
    case 'nt':
      return {
        content: `${triplesToNTriples(triples)}\n`,
        filename: 'triples.nt',
        mime: 'application/n-triples',
      };
    case 'ttl':
      return {
        content: triplesToTurtle(triples),
        filename: 'triples.ttl',
        mime: 'text/turtle',
      };
    case 'owl':
      return {
        content: triplesToTurtle(triples, { ontologyHeader: true }),
        filename: 'triples.owl',
        mime: 'application/owl+xml',
      };
  }
}
