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

/** Conservative text-box footprint, including room for wrapped labels. */
function nodeFootprint(node: GraphNode) {
  return { width: node.properties.is_primary ? 220 : 200, height: Math.max(52, Math.ceil(node.label.length / 20) * 17 + 20) };
}

function graphBounds(nodes: GraphNode[]) {
  return nodes.reduce((bounds, node) => {
    const size = nodeFootprint(node);
    return {
      left: Math.min(bounds.left, (node.x || 0) - size.width / 2),
      right: Math.max(bounds.right, (node.x || 0) + size.width / 2),
      top: Math.min(bounds.top, (node.y || 0) - size.height / 2),
      bottom: Math.max(bounds.bottom, (node.y || 0) + size.height / 2),
    };
  }, { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity });
}

/** Expand only if labels would overlap, rather than reserving a huge empty ring. */
function separateLabels(nodes: GraphNode[]) {
  let scale = 1;
  nodes.forEach((a, index) => {
    const sizeA = nodeFootprint(a);
    for (const b of nodes.slice(index + 1)) {
      const sizeB = nodeFootprint(b);
      const dx = Math.abs((a.x || 0) - (b.x || 0));
      const dy = Math.abs((a.y || 0) - (b.y || 0));
      const required = Math.min(((sizeA.width + sizeB.width) / 2 + 24) / dx, ((sizeA.height + sizeB.height) / 2 + 24) / dy);
      if (Number.isFinite(required)) scale = Math.max(scale, required);
    }
  });
  if (scale > 1) for (const node of nodes) { node.x = (node.x || 0) * scale; node.y = (node.y || 0) * scale; }
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
  if (selected || !system.subsystems.length) {
    const processes = selected?.processes || system.ungrouped;
    const radius = Math.max(180, processes.length * 24);
    processes.forEach((process, index) => {
      const angle = -Math.PI / 2 + 2 * Math.PI * index / processes.length;
      connect(rootId, node(process, 'process', radius * 1.35 * Math.cos(angle), radius * Math.sin(angle)));
    });
  } else {
    const blocks = [...system.subsystems.map(group => ({ term: group.term, processes: group.processes })),
      ...system.ungrouped.map(process => ({ term: null, processes: [process] }))];
    const slots = blocks.reduce((sum, block) => sum + block.processes.length + 1, 0);
    const innerRadius = Math.max(180, blocks.length * 26);
    const outerRadius = Math.max(innerRadius + 170, slots * 10);
    let start = 0;
    for (const block of blocks) {
      const middle = start + block.processes.length / 2;
      const angle = -Math.PI / 2 + 2 * Math.PI * middle / slots;
      const parent = block.term ? node(block.term, 'subsystem', innerRadius * 1.35 * Math.cos(angle), innerRadius * Math.sin(angle)) : rootId;
      if (parent !== rootId) connect(rootId, parent);
      block.processes.forEach((process, index) => {
        const leafAngle = -Math.PI / 2 + 2 * Math.PI * (start + index + 0.5) / slots;
        // Stagger neighbouring leaves to leave room for multi-line process names.
        const stagger = index % 2;
        const radius = outerRadius + stagger * 90;
        connect(parent, node(process, 'process', radius * 1.35 * Math.cos(leafAngle), radius * Math.sin(leafAngle)));
      });
      start += block.processes.length + 1;
    }
  }
  separateLabels(nodes);
  return { rootId, nodes, edges };
}

/** Keep each selected ledger together; never invent a shared ontological parent. */
export function buildSystemsGraph(systems: OntologySystem[]) {
  if (systems.length === 1) return buildSystemGraph(systems[0]);
  const nodes = new Map<string, GraphNode>();
  const edges = new Map<string, GraphEdge>();
  const columns = Math.ceil(Math.sqrt(systems.length));
  const layouts = systems.map(system => {
    const graph = buildSystemGraph(system);
    return { graph, bounds: graphBounds(graph.nodes) };
  });
  const widths = Array.from({ length: columns }, (_, column) => Math.max(...layouts.filter((_, index) => index % columns === column).map(({ bounds }) => bounds.right - bounds.left)));
  const heights = Array.from({ length: Math.ceil(systems.length / columns) }, (_, row) => Math.max(...layouts.slice(row * columns, (row + 1) * columns).map(({ bounds }) => bounds.bottom - bounds.top)));
  layouts.forEach(({ graph, bounds }, index) => {
    const x = widths.slice(0, index % columns).reduce((sum, width) => sum + width + 160, 0) - bounds.left;
    const y = heights.slice(0, Math.floor(index / columns)).reduce((sum, height) => sum + height + 160, 0) - bounds.top;
    for (const node of graph.nodes) {
      if (!nodes.has(node.id)) nodes.set(node.id, { ...node, x: (node.x || 0) + x, y: (node.y || 0) + y });
    }
    for (const edge of graph.edges) edges.set(edge.id, edge);
  });
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}
