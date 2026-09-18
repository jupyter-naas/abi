'use client';

import { create } from 'zustand';

export interface GraphClassSummary {
  class_uri: string;
  class_label: string;
  count: number;
}

/** The network publishes its aggregate schema; the sidebar never queries instances. */
export const useGraphClassCatalog = create<{
  snapshot: {
    workspaceId: string;
    graphId: string;
    graphUri: string;
    graphLabel: string;
    classes: GraphClassSummary[];
    loading: boolean;
    error: string | null;
  } | null;
}>(() => ({ snapshot: null }));
