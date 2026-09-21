'use client';

import { useEffect, useState } from 'react';
import { ontologyTopicIcon, type OntologyTopicSubject } from '@/lib/ontology-topic-icon';
import { cachedIconPaths, iconTarget, iconTargetKey, ICON_PREFIX, loadIconPaths } from '@/lib/ontology-icon-library';
import { useWorkspaceStore } from '@/stores/workspace';
import { useOntologyIconsStore } from '@/stores/ontology-icons';

export function useOntologyIcon(subject: OntologyTopicSubject) {
  const workspaceId = useWorkspaceStore(state => state.currentWorkspaceId);
  const target = iconTarget(subject);
  const key = target ? iconTargetKey(target) : '';
  const override = useOntologyIconsStore(state => state.workspaceId === workspaceId ? state.icons[key] : undefined);
  const fallback = ontologyTopicIcon(subject);
  const name = override?.startsWith(ICON_PREFIX) ? override.slice(ICON_PREFIX.length) : fallback;
  const [, update] = useState(0);
  useEffect(() => {
    let active = true;
    if (!cachedIconPaths(name)) void loadIconPaths([name]).then(() => { if (active) update(value => value + 1); }).catch(() => { /* Keep the suggested glyph if the selected library asset is unavailable. */ });
    return () => { active = false; };
  }, [name]);
  return { name, paths: cachedIconPaths(name) || cachedIconPaths(fallback)! };
}
