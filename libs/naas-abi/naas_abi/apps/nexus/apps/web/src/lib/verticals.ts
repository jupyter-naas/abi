// Vertical registry.
//
// A "vertical" is a locked-down, composable view over the horizontal coding
// primitives (coding environment + agents + source control) targeting one abi
// module's surface, so less-technical users can leverage them for a specific
// use case. New verticals are added here (config) + a view that composes the
// shared primitives — no backend changes (RFC §7.4).

export interface VerticalDef {
  id: string;
  title: string;
  description: string;
  module: string;
  agent: string;
}

export const VERTICALS: VerticalDef[] = [
  {
    id: 'data-pipeline',
    title: 'Data pipeline builder',
    description:
      'Author and review data pipelines for a module without touching the full IDE — an embedded, scoped editor plus a pipeline-savvy agent.',
    module: 'pipelines',
    agent: 'aia',
  },
  {
    id: 'ontology-editor',
    title: 'Ontology editor',
    description:
      'Edit a module ontology with an assistant that understands the knowledge graph, then propose the change for review.',
    module: 'ontology',
    agent: 'aia',
  },
];

export function getVertical(id: string): VerticalDef | undefined {
  return VERTICALS.find((v) => v.id === id);
}
