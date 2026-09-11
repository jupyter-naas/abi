import { useEffect } from 'react';
import { create } from 'zustand';

import type { FeatureResource } from '@/lib/feature-office-agents';

/**
 * The item a feature page has open, for the right chat pane.
 *
 * Slides keeps its own store (`selectedSlug`); every other feature publishes
 * here so the pane can bind that feature's office agent and send the open
 * item as `context.feature.resource` (tools then default to it).
 */
type FeaturePaneState = {
  resource: FeatureResource | null;
  setResource: (resource: FeatureResource | null) => void;
  /** Clear only when `resource` is still the published one. */
  clearResource: (resource: FeatureResource) => void;
};

function sameResource(a: FeatureResource | null, b: FeatureResource): boolean {
  return Boolean(a && a.feature === b.feature && a.kind === b.kind && a.id === b.id);
}

export const useFeaturePaneStore = create<FeaturePaneState>((set) => ({
  resource: null,
  setResource: (resource) => set({ resource }),
  clearResource: (resource) =>
    set((state) => (sameResource(state.resource, resource) ? { resource: null } : state)),
}));

/** Publish the page's open item while it is open; clears on close or unmount. */
export function usePublishFeatureResource(resource: FeatureResource | null): void {
  const feature = resource?.feature;
  const kind = resource?.kind;
  const id = resource?.id;
  const label = resource?.label;
  useEffect(() => {
    if (!feature || !kind || !id) return;
    const published: FeatureResource = { feature, kind, id, ...(label ? { label } : {}) };
    useFeaturePaneStore.getState().setResource(published);
    return () => useFeaturePaneStore.getState().clearResource(published);
  }, [feature, kind, id, label]);
}
