import { systemRoute } from './ontology-navigation';
import { buildOntologySystems, type OntologySystem } from './ontology-system-graph';
import type { DictionaryTerm } from './ontology-dictionary-tree';

/** No explicit selection means all workspace-visible systems. */
export function selectedSystems(query: string): string[] {
  return [...new Set(new URLSearchParams(query).getAll('systemFilter').filter(Boolean))];
}

export function filterSystems(systems: OntologySystem[], query: string): OntologySystem[] {
  const selected = selectedSystems(query);
  return selected.length ? systems.filter(system => selected.includes(system.term.id)) : systems;
}

/**
 * System scope is the union of source files declaring its navigation hierarchy
 * and processes. Null means all workspace files; an empty set means no match.
 * Only workspace-admitted terms contribute paths. Never infer ownership from IRIs.
 */
export function systemOntologyPaths(terms: DictionaryTerm[], query: string): Set<string> | null {
  if (!selectedSystems(query).length) return null;
  const systems = filterSystems(buildOntologySystems(terms), query);
  return new Set(systems.flatMap(system => [system.term, ...system.subsystems.map(group => group.term), ...system.processes])
    .flatMap(term => term.sources?.map(source => source.path) || []));
}

/** Changing scope returns to its overview; drilling down keeps the checkbox selection. */
export function systemFilterRoute(query: string, selected: string[]) {
  const next = systemRoute(query);
  next.delete('systemFilter');
  next.delete('processView');
  [...new Set(selected)].sort().forEach(id => next.append('systemFilter', id));
  return next;
}
