'use client';

import { useMemo, useRef, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useOntologyDictionaryStore } from '@/stores/ontology-dictionary';
import { useWorkspaceStore } from '@/stores/workspace';
import { buildOntologySystems } from '@/lib/ontology-system-graph';
import { selectedSystems, systemFilterRoute } from '@/lib/ontology-system-filter';
import { systemRoute } from '@/lib/ontology-navigation';
import { OntologyMultiPicker } from './ontology-multi-picker';
import { getWorkspacePath } from './utils';

/** The same full-width checkbox picker as ontology files, with an overview shortcut. */
export function OntologySystemPicker() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params?.toString() || '';
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const dictionary = useOntologyDictionaryStore();
  const ready = dictionary.workspaceId === workspaceId;
  const systems = useMemo(() => ready ? buildOntologySystems(dictionary.terms) : [], [ready, dictionary.terms]);
  const value = selectedSystems(query);
  const latestQuery = useRef(query);
  useEffect(() => { latestQuery.current = query; }, [query]);
  function toggle(id?: string) {
    const current = selectedSystems(latestQuery.current);
    const next = !id ? [] : current.includes(id) ? current.filter(value => value !== id) : [...current, id];
    const route = systemFilterRoute(latestQuery.current, next);
    latestQuery.current = route.toString();
    router.push(getWorkspacePath(workspaceId, `/ontology?${route}`), {scroll: false});
  }
  const label = !value.length ? 'All systems' : value.length === 1 ? systems.find(system => system.term.id === value[0])?.term.name || 'Selected system' : `${value.length} systems selected`;
  return <OntologyMultiPicker key={workspaceId} items={systems.map(system => ({value: system.term.id, label: system.term.name, detail: `${system.processes.length} processes`}))}
      value={value} onToggle={toggle} onClear={() => toggle()} loading={!ready || dictionary.loading} error={ready ? dictionary.error : null}
      label={label} noun="systems" allLabel="All systems"
      action={{ label: 'Open system overview', onClick: () => router.push(getWorkspacePath(workspaceId, `/ontology?${systemRoute(latestQuery.current)}`), {scroll: false}) }} />;
}
