import type { GraphEdge, GraphNode } from '../stores/knowledge-graph';
import { ONTOLOGY_SPACING, ontologySpacing, ontologySpacingRoute } from './ontology-spacing';

export type GraphNodeShape = 'circle' | 'square';
export type GraphConnectors = 'orthogonal' | 'curved';
export type GraphLayoutDirection = 'TD' | 'LR';

export const INSTANCE_NODE_SIZE = 18;
export const INSTANCE_NODE_FONT = 11;

const RDF_NS = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';
const RDFS_NS = 'http://www.w3.org/2000/01/rdf-schema#';
const OWL_NS = 'http://www.w3.org/2002/07/owl#';
const INSTANCE_OWL_PREDICATES = new Set(['sameAs', 'differentFrom']);

/** OWL/RDFS/RDF metatypes. These are ontology terms, not graph individuals. */
export const SCHEMA_TYPE_URIS = new Set([
  `${OWL_NS}Class`,
  `${RDFS_NS}Class`,
  `${OWL_NS}Ontology`,
  `${OWL_NS}ObjectProperty`,
  `${OWL_NS}DatatypeProperty`,
  `${OWL_NS}AnnotationProperty`,
  `${RDF_NS}Property`,
  `${RDFS_NS}Datatype`,
  `${OWL_NS}Restriction`,
  `${OWL_NS}Axiom`,
  `${OWL_NS}TransitiveProperty`,
  `${OWL_NS}FunctionalProperty`,
  `${OWL_NS}InverseFunctionalProperty`,
  `${OWL_NS}SymmetricProperty`,
  `${OWL_NS}AsymmetricProperty`,
  `${OWL_NS}ReflexiveProperty`,
  `${OWL_NS}IrreflexiveProperty`,
  `${OWL_NS}DeprecatedProperty`,
  `${OWL_NS}DeprecatedClass`,
  `${OWL_NS}OntologyProperty`,
]);

export function localIriName(uri: string) {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

export function isW3cSchemaIri(uri: string) {
  return uri.startsWith(RDF_NS) || uri.startsWith(RDFS_NS) || uri.startsWith(OWL_NS);
}

export function isSchemaTypeUri(uri: string) {
  return SCHEMA_TYPE_URIS.has(uri);
}

/** rdfs:range, owl:equivalentProperty, and other schema links. owl:sameAs between people stays. */
export function isSchemaPredicate(uri: string, label = '') {
  const name = localIriName(uri) || label.replace(/\s+/g, '');
  if (isW3cSchemaIri(uri)) return !INSTANCE_OWL_PREDICATES.has(name);
  return /^(range|domain|subClassOf|subPropertyOf|equivalentProperty|equivalentClass|inverseOf)$/i.test(name);
}

export function isSchemaInstanceNode(node: GraphNode, keepIds?: Set<string>) {
  if (keepIds?.has(node.id)) return false;
  const uri = String(node.properties?.uri || node.id);
  if (isW3cSchemaIri(uri)) return true;
  return isSchemaTypeUri(String(node.properties?.class_uri || node.type || ''));
}

/** Individuals and instance relations only. Schema terms stay on Ontology. */
export function toInstanceNetwork(
  nodes: GraphNode[],
  edges: GraphEdge[],
  keepIds?: Set<string>,
) {
  const visible = nodes.filter(node => !isSchemaInstanceNode(node, keepIds));
  const ids = new Set(visible.map(node => node.id));
  return {
    nodes: visible,
    edges: edges.filter(edge =>
      ids.has(edge.source)
      && ids.has(edge.target)
      && !edge.properties?.layout_only
      && !isSchemaPredicate(edge.type || '', edge.label || ''),
    ),
  };
}

export function explorerResourceId(graph: string, uri: string) {
  return JSON.stringify([graph, uri]);
}

export function explorerInstanceGraph(data: {
  items: Array<{ uri: string; graph_uri?: string; label?: string; class_label?: string; class_uri?: string; properties?: Record<string, string> }>;
  neighbors?: Array<{ uri: string; graph_uri?: string; label?: string; class_label?: string; class_uri?: string; properties?: Record<string, string> }>;
  relations?: Array<{ graph_uri: string; source: string; target: string; predicate: string; label: string }>;
}) {
  const resources = new Map<string, {
    uri: string;
    graph_uri: string;
    label?: string;
    class_label?: string;
    class_uri?: string;
    properties: Record<string, string>;
  }>();
  const seeds = new Set<string>();
  for (const instance of [...data.items, ...(data.neighbors || [])]) {
    if (!instance.graph_uri) continue;
    const id = explorerResourceId(instance.graph_uri, instance.uri);
    const seed = data.items.some(item => item.graph_uri === instance.graph_uri && item.uri === instance.uri);
    if (!seed && (isSchemaTypeUri(instance.class_uri || '') || isW3cSchemaIri(instance.uri))) continue;
    if (seed) seeds.add(id);
    if (!resources.has(id)) {
      resources.set(id, { ...instance, graph_uri: instance.graph_uri, properties: instance.properties || {} });
    }
  }
  const nodes: GraphNode[] = [...resources].map(([id, instance]) => ({
    id,
    label: instance.label || instance.uri,
    type: instance.class_label || 'Resource',
    properties: {
      uri: instance.uri,
      graph_uri: instance.graph_uri,
      class_uri: instance.class_uri,
      is_primary: seeds.has(id),
    },
  }));
  const edges: GraphEdge[] = (data.relations || [])
    .filter(relation => !isSchemaPredicate(relation.predicate, relation.label))
    .map(relation => ({
      id: JSON.stringify([relation.graph_uri, relation.source, relation.predicate, relation.target]),
      source: explorerResourceId(relation.graph_uri, relation.source),
      target: explorerResourceId(relation.graph_uri, relation.target),
      type: relation.predicate,
      label: relation.label,
    }))
    .filter(edge => resources.has(edge.source) && resources.has(edge.target));
  return { nodes, edges, resources, seeds };
}

/** Graph defaults to circles. Ontology keeps squares via its own canvas. */
export function graphNodeShape(query: string): GraphNodeShape {
  return new URLSearchParams(query).get('nodes') === 'square' ? 'square' : 'circle';
}

export function graphConnectors(query: string): GraphConnectors {
  return new URLSearchParams(query).get('connectors') === 'curved' ? 'curved' : 'orthogonal';
}

export function graphSpacing(query: string) {
  return ontologySpacing(query);
}

/** Presentation settings stay on the current explorer or instance URL. */
export function graphNetworkRoute(
  query: string,
  changes: { connectors?: string; spacing?: string; nodes?: string },
) {
  let params = new URLSearchParams(query);
  if (changes.spacing) params = new URLSearchParams(ontologySpacingRoute(params.toString(), changes.spacing));
  if (changes.connectors) params.set('connectors', changes.connectors === 'curved' ? 'curved' : 'orthogonal');
  if (changes.nodes) params.set('nodes', changes.nodes === 'square' ? 'square' : 'circle');
  return params;
}

export function wrapInstanceLabel(label: string, maxChars = 18, maxLines = 2): string[] {
  const words = (label || '').trim().replace(/\s+/g, ' ').split(' ').filter(Boolean);
  if (!words.length) return [''];
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars) {
      current = next;
      continue;
    }
    if (current) lines.push(current);
    current = word.length > maxChars ? word.slice(0, maxChars) : word;
    if (lines.length >= maxLines) break;
  }
  if (lines.length < maxLines && current) lines.push(current);
  return lines.slice(0, maxLines);
}

/**
 * vis-network draws `dot` / `square` labels below the node (`y + height/2 + labelHeight/2`,
 * hanging baseline). A negative `font.vadjust` shifts that label above the node.
 */
export function instanceLabelVAdjust(
  size = INSTANCE_NODE_SIZE,
  lineCount = 1,
  fontSize = INSTANCE_NODE_FONT,
  gap = 8,
) {
  const labelHeight = Math.max(1, lineCount) * fontSize * 1.2;
  return -(size * 2 + labelHeight * 1.5 + gap);
}

export function instanceNodeCtxRenderer(opts: {
  circular: boolean;
  textColor: string;
  strokeColor: string;
}) {
  return ({
    ctx,
    x,
    y,
    style,
    label,
  }: {
    ctx: CanvasRenderingContext2D;
    x: number;
    y: number;
    style: { size?: number; color?: string; borderColor?: string; borderWidth?: number };
    label?: string;
  }) => {
    const radius = style.size || INSTANCE_NODE_SIZE;
    const lines = String(label || '').split('\n').filter(Boolean);
    return {
      drawNode() {
        ctx.beginPath();
        if (opts.circular) ctx.arc(x, y, radius, 0, Math.PI * 2);
        else ctx.rect(x - radius, y - radius, radius * 2, radius * 2);
        ctx.fillStyle = style.color || '#6b7280';
        ctx.fill();
        ctx.lineWidth = style.borderWidth || 2;
        ctx.strokeStyle = style.borderColor || '#4b5563';
        ctx.stroke();
      },
      drawExternalLabel() {
        ctx.font = `600 ${INSTANCE_NODE_FONT}px Inter, system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.lineJoin = 'round';
        const gap = 8;
        const lineHeight = 14;
        lines.forEach((line, index) => {
          const lineY = y - radius - gap - (lines.length - 1 - index) * lineHeight;
          ctx.lineWidth = 3;
          ctx.strokeStyle = opts.strokeColor;
          ctx.strokeText(line, x, lineY);
          ctx.fillStyle = opts.textColor;
          ctx.fillText(line, x, lineY);
        });
      },
      nodeDimensions: { width: radius * 2, height: radius * 2 },
    };
  };
}

export function instanceNodeLayoutBox(label: string, primary = false) {
  const lines = wrapInstanceLabel(label);
  const size = primary ? INSTANCE_NODE_SIZE + 4 : INSTANCE_NODE_SIZE;
  const longest = Math.max(...lines.map(line => line.length), 4);
  return {
    width: Math.max(size * 2 + 16, Math.ceil(longest * 6.4)),
    height: size * 2 + lines.length * 14 + 10,
  };
}

export function filterInstanceNetwork(
  nodes: GraphNode[],
  edges: GraphEdge[],
  opts: {
    search?: string;
    objectProperties?: boolean;
    focusedId?: string | null;
    hiddenIds?: Set<string>;
    activeBuckets?: Set<string>;
    bucketOf?: (node: GraphNode) => string;
  } = {},
) {
  const query = (opts.search || '').trim().toLowerCase();
  let visible = nodes.filter(node => !opts.hiddenIds?.has(node.id));
  if (query) {
    visible = visible.filter(node =>
      node.label.toLowerCase().includes(query)
      || node.id.toLowerCase().includes(query)
      || (node.type || '').toLowerCase().includes(query)
      || String(node.properties?.uri || node.properties?.iri || '').toLowerCase().includes(query),
    );
  }
  if (opts.activeBuckets && opts.activeBuckets.size > 0) {
    const bucketOf = opts.bucketOf || (node => node.type || 'Unknown');
    visible = visible.filter(node => opts.activeBuckets!.has(bucketOf(node)));
  }
  if (opts.focusedId) {
    const keep = new Set<string>([opts.focusedId]);
    for (const edge of edges) {
      if (edge.properties?.layout_only) continue;
      if (edge.source === opts.focusedId) keep.add(edge.target);
      if (edge.target === opts.focusedId) keep.add(edge.source);
    }
    visible = visible.filter(node => keep.has(node.id));
  }
  const ids = new Set(visible.map(node => node.id));
  const visibleEdges = opts.objectProperties === false
    ? []
    : edges.filter(edge =>
        ids.has(edge.source) && ids.has(edge.target) && !edge.properties?.layout_only);
  return { nodes: visible, edges: visibleEdges };
}

/** Synthetic child→parent edges so TD/LR can stack an ego graph without OWL subclassOf. */
export function instanceLayoutEdges(nodes: GraphNode[], rootId?: string | null): GraphEdge[] {
  const root = nodes.find(node => node.id === rootId)
    || nodes.find(node => node.properties?.is_primary === true)
    || nodes[0];
  if (!root) return [];
  return nodes.filter(node => node.id !== root.id).map(node => ({
    id: `layout:${node.id}:${root.id}`,
    source: node.id,
    target: root.id,
    type: 'layout',
    properties: { relation_kind: 'is_a', layout_only: true },
  }));
}

export { ONTOLOGY_SPACING };
