/**
 * The ontology payload as a network: terms (classes), and the relations between
 * them in the three families the Nexus ontology network lets you switch on and
 * off. Nothing here touches the DOM.
 */

/** ``subClassOf`` is the hierarchy; a restriction and an object property are the rest. */
export const RELATIONS = {
  subClassOf: "hierarchy",
  restriction: "restriction",
  objectProperty: "property",
};

/** ``abi:genericallyDependsOn (someValuesFrom)`` reads as ``genericallyDependsOn · some``. */
export function relationLabel(edge) {
  if (edge.kind === "subClassOf") return "subclass of";
  const text = String(edge.label ?? "");
  const match = /^(?:[\w-]+:)?(.+?)\s*\((someValuesFrom|allValuesFrom|hasValue|cardinality)\)$/.exec(text);
  if (!match) return text;
  const quantifier = { someValuesFrom: "some", allValuesFrom: "only", hasValue: "value", cardinality: "exactly" }[match[2]];
  return `${match[1]} · ${quantifier}`;
}

/**
 * Two relations between the same two terms, one each way (``has skill`` and
 * ``is skill of``), are one connection with an arrow at each end: drawn apart
 * they would be two lines side by side saying the same thing.
 */
export function mergeReciprocal(edges) {
  const merged = [];
  const open = new Map();
  for (const edge of [...edges].sort((a, b) => a.label.localeCompare(b.label))) {
    if (edge.relation === "hierarchy" || edge.source === edge.target) {
      merged.push(edge);
      continue;
    }
    // Look for the relation that runs the other way.
    const key = JSON.stringify([edge.target, edge.source, edge.relation]);
    const waiting = open.get(key);
    if (waiting?.length) {
      const first = waiting.shift();
      merged.push({ ...first, id: JSON.stringify([first.id, edge.id]), label: `${first.label} / ${edge.label}`, both: true });
      continue;
    }
    const own = JSON.stringify([edge.source, edge.target, edge.relation]);
    if (!open.has(own)) open.set(own, []);
    open.get(own).push(edge);
  }
  for (const waiting of open.values()) merged.push(...waiting);
  return merged;
}

/** Terms and connections, each edge with a stable id and the family it belongs to. */
export function buildOntologyGraph(payload) {
  const nodes = (payload.graph?.nodes || []).map((node) => ({
    id: node.id,
    iri: node.iri,
    label: node.label,
    bucket: node.bfo_bucket || "Unknown",
  }));
  const known = new Set(nodes.map((node) => node.id));
  const edges = new Map();
  for (const edge of payload.graph?.edges || []) {
    if (!known.has(edge.from) || !known.has(edge.to)) continue;
    const relation = RELATIONS[edge.kind] || "property";
    const label = relationLabel(edge);
    const id = JSON.stringify([edge.from, edge.to, edge.kind, label]);
    if (!edges.has(id)) edges.set(id, { id, source: edge.from, target: edge.to, label, relation });
  }
  return { nodes, edges: mergeReciprocal([...edges.values()]) };
}

const isWanted = ({ hierarchy, restrictions, properties }) => (edge) =>
  edge.relation === "hierarchy" ? hierarchy : edge.relation === "restriction" ? restrictions : properties;

/**
 * The terms a connection in the families that are on reaches, within ``keep``
 * (the terms of one file, or every term when null). A class a file names is not
 * one of them when the only thing linking it to the others is a family that is
 * off: ``Role`` is in a process slice as ``subClassOf abi:Role``, so with the
 * hierarchy off it has nothing to be drawn with. The bucket and hand filters
 * do not change this, so the bucket panel can list the same terms.
 */
export function connectedNodes(graph, families, keep = null) {
  const wanted = isWanted(families);
  const inFile = (id) => !keep || keep.has(id);
  const linked = new Set();
  for (const edge of graph.edges) {
    if (wanted(edge) && inFile(edge.source) && inFile(edge.target)) {
      linked.add(edge.source);
      linked.add(edge.target);
    }
  }
  return graph.nodes.filter((node) => linked.has(node.id));
}

/**
 * What is drawn: the connected terms, only those in the chosen buckets and not
 * hidden by hand, and the connections among them.
 */
export function filterGraph(graph, families, buckets = new Set(), hidden = new Set(), keep = null) {
  const wanted = isWanted(families);
  const nodes = connectedNodes(graph, families, keep).filter((node) => (!buckets.size || buckets.has(node.bucket)) && !hidden.has(node.id));
  const shown = new Set(nodes.map((node) => node.id));
  return { nodes, edges: graph.edges.filter((edge) => wanted(edge) && shown.has(edge.source) && shown.has(edge.target)) };
}

/** The terms of one bucket, by name, for the bucket panel's checklist. */
export function nodesPerBucket(nodes) {
  const buckets = new Map();
  for (const node of nodes) {
    const entries = buckets.get(node.bucket) || [];
    entries.push({ id: node.id, label: node.label });
    buckets.set(node.bucket, entries);
  }
  for (const entries of buckets.values()) entries.sort((a, b) => a.label.localeCompare(b.label));
  return buckets;
}

/** What one term is connected to in the current view, and in which direction. */
export function connectionsOf(nodeId, nodes, edges) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  return edges
    .filter((edge) => edge.source === nodeId || edge.target === nodeId)
    .flatMap((edge) => {
      const other = byId.get(edge.source === nodeId ? edge.target : edge.source);
      return other ? [{ edge, other, incoming: edge.target === nodeId }] : [];
    });
}

/**
 * The terms a source file declares. A file is a slice of the vocabulary, so it
 * is read as text: a term belongs to it when the file names it as ``x a ...``,
 * gives it properties (``x;``) or mentions its qname.
 */
export function termsInSource(text, nodes) {
  const found = new Set();
  for (const node of nodes) {
    const local = node.id.includes(":") ? node.id.split(":").pop() : node.id;
    if (text.includes(node.id) || text.includes(`${local} a `) || text.includes(`${local};`) || text.includes(`${local} `)) {
      found.add(node.id);
    }
  }
  return found;
}
