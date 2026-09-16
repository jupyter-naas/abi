import type { DictionaryTerm } from './ontology-dictionary-tree';
import type { TermGraph } from './ontology-term-graph';
import { termKey } from './ontology-context';
import { type BfoBucketDef } from './bfo-buckets';

const ABI = 'http://ontology.naas.ai/abi/';
const BFO = 'http://purl.obolibrary.org/obo/';
// Source ledger palette; formal Ontology mode keeps the platform BFO palette.
const PALETTE: Record<string, { color: string; fill: string }> = {
  WHAT: { color: '#2E86C1', fill: '#D6EAF8' },
  WHO: { color: '#1E8449', fill: '#D5F5E3' },
  WHERE: { color: '#D4AC0D', fill: '#FEF9E7' },
  WHEN: { color: '#8E44AD', fill: '#F4ECF7' },
  HOWITIS: { color: '#717D7E', fill: '#EAECEE' },
  WHY: { color: '#1A5276', fill: '#D0E3EE' },
  HOWWEKNOW: { color: '#BA4A00', fill: '#FDEBD0' },
};
const BUCKETS = [
  { key: 'WHO', label: 'Who', style: 'Material Entity', description: 'Actors and systems', relation: 'has participant', properties: [BFO + 'BFO_0000057', ABI + 'usesInformation'] },
  { key: 'WHERE', label: 'Where', style: 'Site', description: 'Places and settings', relation: 'occurs in', properties: [BFO + 'BFO_0000066'] },
  { key: 'WHEN', label: 'When', style: 'Temporal Region', description: 'Triggers and cadence', relation: 'occupies temporal region', properties: [ABI + 'hasExecutionCondition', BFO + 'BFO_0000199'] },
  { key: 'HOWITIS', label: 'How it is', style: 'Quality', description: 'Status and indicators', relation: 'has quality', properties: [ABI + 'hasIndicatorRecord'] },
  { key: 'WHY', label: 'Why', style: 'Realizable', description: 'Objectives and intended outcomes', relation: 'realizes', properties: [ABI + 'pursuesObjective', BFO + 'BFO_0000055'] },
  { key: 'HOWWEKNOW', label: 'How we know', style: 'GDC', description: 'Records and evidence', relation: 'documented by', properties: [ABI + 'documentedBy', BFO + 'BFO_0000059'] },
];

// These are presentation categories. Their identifiers deliberately are not BFO types.
export const PROCESS_BUCKET_DEFS: BfoBucketDef[] = [
  { uri: '', type: 'ledger:WHAT', label: 'What', description: 'The selected process', color: PALETTE.WHAT.color, border: PALETTE.WHAT.color },
  ...BUCKETS.map(bucket => ({ uri: '', type: `ledger:${bucket.key}`, label: bucket.label, description: bucket.description, color: PALETTE[bucket.key].color, border: PALETTE[bucket.key].color })),
];

/** Project source annotations only; no ancestors, inherited relations or fabricated classes. */
export function buildProcessGraph(term: DictionaryTerm, terms: DictionaryTerm[]): TermGraph | null {
  if (term.type !== 'entity' || !term.processLedger || !Object.values(term.processLedger.buckets).some(values => values.length)) return null;
  const rootId = termKey(term);
  const graph: TermGraph = { rootId, nodes: [{
    id: rootId, label: `${term.processLedger.code ? term.processLedger.code + ' · ' : ''}${term.name}`,
    type: 'ledger:WHAT', color: PALETTE.WHAT.color, x: 0, y: 0,
    properties: { overview_fill: PALETTE.WHAT.fill, iri: term.id, formal_term_id: rootId, is_primary: true, kind: 'Process', definition: term.description || '', source_files: term.sources || [] },
  }], edges: [] };
  const classes = new Map(terms.filter(item => item.type === 'entity').map(item => [item.id, item]));
  const properties = new Map(terms.filter(item => item.type === 'relationship').map(item => [item.id, item]));
  function matchesProperty(id: string, expected: string[]) {
    const pending = [id]; const seen = new Set<string>();
    while (pending.length) {
      const next = pending.pop()!;
      if (expected.includes(next)) return true;
      if (seen.has(next)) continue;
      seen.add(next);
      pending.push(...(properties.get(next)?.parents || []).map(parent => parent.id));
    }
    return false;
  }
  BUCKETS.forEach((bucket, group) => {
    const entries = term.processLedger!.buckets[bucket.key] || [];
    const values = [...new Set(entries.map(entry => entry.value))].sort((a, b) => a.localeCompare(b));
    values.forEach((value, index) => {
      const id = `ledger:${JSON.stringify([term.id, bucket.key, value])}`;
      const angle = group * Math.PI / 3 - Math.PI / 2 + (index - (values.length - 1) / 2) * 0.17;
      const radius = 320 + index * 160;
      const sources = [...new Map(entries.filter(entry => entry.value === value).flatMap(entry => entry.sources).map(source => [source.path, source])).values()];
      // Link only a direct declared target with explicit matching wording. An
      // unmatched source label can still open the whole process ontology.
      const matches = [...new Set((term.relations || []).filter(relation => matchesProperty(relation.property.id, bucket.properties))
        .map(relation => relation.target.id))].map(iri => classes.get(iri)).filter((target): target is DictionaryTerm => Boolean(target && (target.sourceValues?.includes(value) || target.name === value)));
      const target = matches.length === 1 ? matches[0] : undefined;
      const color = PALETTE[bucket.key].color;
      graph.nodes.push({
        id, label: value, type: `ledger:${bucket.key}`, color,
        x: Math.cos(angle) * radius, y: Math.sin(angle) * radius,
        properties: { overview_fill: PALETTE[bucket.key].fill, kind: 'Ledger entry', presentation_only: true, ledger_bucket: bucket.label,
          definition: target?.description || `${bucket.label} in the source process ledger.`,
          formal_term_id: target ? termKey(target) : undefined, iri: target?.id,
          source_files: sources },
      });
      graph.edges.push({ id: `ledger-edge:${id}`, source: rootId, target: id, type: 'ledger connection', label: bucket.relation,
        properties: { relation_kind: 'ledger', presentation_only: true, color, source_files: sources } });
    });
  });
  return graph;
}

/** Keep process, subsystem and accumulated file filters when changing presentation. */
export function processPresentationRoute(query: string, presentation: 'process' | 'ontology'): URLSearchParams {
  const next = new URLSearchParams(query);
  if (presentation === 'ontology') next.set('processView', 'ontology');
  else next.delete('processView');
  return next;
}
