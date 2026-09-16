'use client';

import { useEffect } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import { useOntologySystemTreeStore, type SystemTreeProjection } from '@/stores/ontology-system-tree';

export function useOntologySystemTreeScope() {
  const pathname = usePathname();
  const params = useSearchParams();
  return `${pathname}?${params?.toString() || ''}`;
}

export function usePublishOntologySystemTree(enabled: boolean, projection: SystemTreeProjection) {
  const scope = useOntologySystemTreeScope();
  const { nodes, edges, selectedNodeId, onSelect, onOpen, canOpen, openLabel, bucketDefinitions, bucketHeading } = projection;
  useEffect(() => {
    if (!enabled) return;
    const owner = {};
    useOntologySystemTreeStore.getState().publish({ scope, owner, nodes, edges, selectedNodeId, onSelect, onOpen, canOpen, openLabel, bucketDefinitions, bucketHeading });
    return () => useOntologySystemTreeStore.getState().release(owner);
  }, [enabled, scope, nodes, edges, selectedNodeId, onSelect, onOpen, canOpen, openLabel, bucketDefinitions, bucketHeading]);
}
