import { systemRoute } from './ontology-navigation';
import type { OntologySystem } from './ontology-system-graph';

/** No explicit selection means all workspace-visible systems. */
export function selectedSystems(query: string): string[] {
  return [...new Set(new URLSearchParams(query).getAll('systemFilter').filter(Boolean))];
}

export function filterSystems(systems: OntologySystem[], query: string): OntologySystem[] {
  const selected = selectedSystems(query);
  return selected.length ? systems.filter(system => selected.includes(system.term.id)) : systems;
}

/** Changing scope returns to its overview; drilling down keeps the checkbox selection. */
export function systemFilterRoute(query: string, selected: string[]) {
  const next = systemRoute(query);
  next.delete('systemFilter');
  next.delete('processView');
  [...new Set(selected)].sort().forEach(id => next.append('systemFilter', id));
  return next;
}
