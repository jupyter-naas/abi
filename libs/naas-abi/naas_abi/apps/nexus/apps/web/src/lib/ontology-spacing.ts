import type { GraphNode } from '../stores/knowledge-graph';

export const ONTOLOGY_SPACING = [
  { value: 'compact', label: 'Compact', gap: 40, scale: 1 },
  { value: 'comfortable', label: 'Comfortable', gap: 80, scale: 1.3 },
  { value: 'spacious', label: 'Spacious', gap: 140, scale: 1.7 },
] as const;

export type OntologySpacingValue = (typeof ONTOLOGY_SPACING)[number]['value'];

export function ontologySpacing(
  query: string,
  fallback: OntologySpacingValue = 'compact',
) {
  const value = new URLSearchParams(query).get('spacing');
  return (
    ONTOLOGY_SPACING.find(option => option.value === value) ||
    ONTOLOGY_SPACING.find(option => option.value === fallback) ||
    ONTOLOGY_SPACING[0]
  );
}

/** Presentation settings preserve selected systems, files, process and inspected term. */
export function ontologySpacingRoute(query: string, value: string) {
  const params = new URLSearchParams(query);
  params.set('spacing', ONTOLOGY_SPACING.find(option => option.value === value)?.value || 'compact');
  return params;
}

/** Spread an existing radial overview without changing card sizes or its group structure. */
export function spaceOntologyNodes(nodes: GraphNode[], scale: number): GraphNode[] {
  if (scale === 1) return nodes;
  return nodes.map(node => ({ ...node,
    x: node.x === undefined ? undefined : node.x * scale,
    y: node.y === undefined ? undefined : node.y * scale,
  }));
}
