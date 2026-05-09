/**
 * Shared types for the ontology page and its `_components/` siblings.
 *
 * These shapes match what the API returns through the typed `apiFetch` /
 * Zod schemas in `lib/api/ontology.ts` — but with non-optional `properties`
 * so consumer code doesn't have to litter `?? {}` everywhere.
 */

export type ViewMode =
  | 'overview'
  | 'network'
  | 'classes'
  | 'relations'
  | 'editor'
  | 'import'
  | 'export'
  | 'create-entity'
  | 'create-relationship';

export type OntologyOverviewGraphNode = {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
};

export type OntologyOverviewGraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string;
  properties?: Record<string, unknown>;
};

export type OntologyOverviewStats = {
  name: string;
  path: string;
  total_items: number;
  classes: number;
  relationships: number;
  data_properties: number;
  named_individuals: number;
};
