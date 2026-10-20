'use client';

import { create } from 'zustand';
import type { BfoBucketDef } from '@/lib/bfo-buckets';
import type { GraphNode, GraphEdge } from './knowledge-graph';

export type SystemTreeProjection = {
  bucketDefinitions?: BfoBucketDef[];
  bucketHeading?: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
  canOpen: (id: string) => boolean;
  openLabel: string;
};

type Registration = SystemTreeProjection & { scope: string; owner: object };

// The active canvas supplies its own graph and actions to the shell sidebar.
// The route scope prevents a previous workspace or process from flashing on navigation.
export const useOntologySystemTreeStore = create<{
  current: Registration | null;
  publish: (registration: Registration) => void;
  release: (owner: object) => void;
}>((set) => ({
  current: null,
  publish: current => set({ current }),
  release: owner => set(state => state.current?.owner === owner ? { current: null } : state),
}));
