import type { DictionaryTerm } from './ontology-dictionary-tree';
import type { GraphNode, GraphEdge } from '../stores/knowledge-graph';
import { termKey } from './ontology-context';

export type OntologySubsystem = { term: DictionaryTerm; processes: DictionaryTerm[] };
export type OntologySystem = { term: DictionaryTerm; subsystems: OntologySubsystem[]; processes: DictionaryTerm[]; ungrouped: DictionaryTerm[] };
const compare = (a: DictionaryTerm, b: DictionaryTerm) => systemProcessLabel(a).localeCompare(systemProcessLabel(b), undefined, { numeric: true });

/** Navigation groupings are explicitly declared; only admitted workspace terms are used. */
export function buildOntologySystems(terms: DictionaryTerm[], scopedTerms = terms): OntologySystem[] {
  const classes = terms.filter(term => term.type === 'entity');
  const byId = new Map(classes.map(term => [term.id, term]));
  function isProcess(term: DictionaryTerm) {
    const pending = [term.id]; const seen = new Set<string>();
    while (pending.length) {
      const id = pending.pop()!;
      if (id === 'http://purl.obolibrary.org/obo/BFO_0000015') return true;
      if (seen.has(id)) continue;
      seen.add(id);
      pending.push(...(byId.get(id)?.parents || []).map(parent => parent.id), ...(byId.get(id)?.equivalents || []).map(parent => parent.id));
    }
    return false;
  }
  const candidates = scopedTerms.filter(term => term.type === 'entity' && !term.systemViewKind && isProcess(term));
  return classes.filter(term => term.systemViewKind === 'system').sort(compare).map(term => {
    const subsystems = classes.filter(group => group.systemViewKind === 'subsystem' && group.systemViewParents?.some(parent => parent.id === term.id))
      .sort(compare).map(group => ({ term: group, processes: candidates.filter(process => process.parents?.some(parent => parent.id === group.id)).sort(compare) }));
    const grouped = new Set(subsystems.flatMap(group => group.processes.map(process => process.id)));
    const ungrouped = candidates.filter(process => !grouped.has(process.id) && process.parents?.some(parent => parent.id === term.id)).sort(compare);
    const processes = [...new Map([...subsystems.flatMap(group => group.processes), ...ungrouped].map(process => [process.id, process])).values()].sort(compare);
    return { term, subsystems: subsystems.filter(group => group.processes.length > 0), processes, ungrouped };
  });
}

export function systemProcessLabel(term: DictionaryTerm): string {
  const code = term.aliases?.find(alias => /^S\d+-P\d+$/.test(alias));
  return code ? `${code} · ${term.name}` : term.name;
}

/** Fixed radial layout: centre → declared subsystems → their actual process classes. */
export function buildSystemGraph(system: OntologySystem, subsystemId?: string) {
  const selected = system.subsystems.find(group => group.term.id === subsystemId);
  const root = selected?.term || system.term;
  const rootId = termKey(root);
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();
  function node(term: DictionaryTerm, level: 'system' | 'subsystem' | 'process', x: number, y: number) {
    const id = termKey(term);
    if (seen.has(id)) return id;
    seen.add(id);
    nodes.push({ id, label: level === 'process' ? systemProcessLabel(term) : term.name, type: 'Process', x, y,
      properties: { iri: term.id, term_type: term.type, system_level: level, is_primary: id === rootId, definition: term.description || '', source_files: term.sources || [] } });
    return id;
  }
  function connect(parent: string, child: string) {
    edges.push({ id: JSON.stringify([parent, child]), source: parent, target: child, type: 'Navigation grouping', properties: { relation_kind: 'system_group' } });
  }
  node(root, selected ? 'subsystem' : 'system', 0, 0);
  if (selected) {
    selected.processes.forEach((process, index) => {
      const angle = -Math.PI / 2 + 2 * Math.PI * index / selected.processes.length;
      connect(rootId, node(process, 'process', 380 * Math.cos(angle), 300 * Math.sin(angle)));
    });
  } else {
    const blocks = [...system.subsystems.map(group => ({ term: group.term, processes: group.processes })),
      ...system.ungrouped.map(process => ({ term: null, processes: [process] }))];
    const slots = blocks.reduce((sum, block) => sum + block.processes.length + 1, 0);
    let start = 0;
    for (const block of blocks) {
      const middle = start + block.processes.length / 2;
      const angle = -Math.PI / 2 + 2 * Math.PI * middle / slots;
      const parent = block.term ? node(block.term, 'subsystem', 490 * Math.cos(angle), 380 * Math.sin(angle)) : rootId;
      if (parent !== rootId) connect(rootId, parent);
      block.processes.forEach((process, index) => {
        const leafAngle = -Math.PI / 2 + 2 * Math.PI * (start + index + 0.5) / slots;
        // Stagger neighbouring leaves to leave room for multi-line process names.
        const stagger = index % 2;
        connect(parent, node(process, 'process', (1100 + stagger * 140) * Math.cos(leafAngle), (860 + stagger * 110) * Math.sin(leafAngle)));
      });
      start += block.processes.length + 1;
    }
  }
  return { rootId, nodes, edges };
}
