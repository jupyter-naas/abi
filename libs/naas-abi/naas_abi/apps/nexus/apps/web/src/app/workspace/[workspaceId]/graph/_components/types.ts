/**
 * Shared types for the graph page and its `_components/` siblings.
 *
 * Visualization-shape types — the page already maps the API responses
 * (validated through Zod in `lib/api/graph.ts`) into these shapes for
 * vis-network and other UI surfaces.
 */

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  sourceLabel?: string;
  targetLabel?: string;
  type: string;
  label?: string;
  properties?: Record<string, unknown>;
}

export interface GraphOption {
  id: string;
  name: string;
}

export interface FilterOption {
  uri: string;
  label: string;
}

export interface OntologyClassOption {
  id: string;
  name: string;
  description: string;
}

export interface ViewFilterDraft {
  subject_uri: string;
  predicate_uri: string;
  object_uri: string;
}

export type GraphPageMode =
  | 'graph'
  | 'create-individual'
  | 'create-view'
  | 'create-graph'
  | 'sparql';
