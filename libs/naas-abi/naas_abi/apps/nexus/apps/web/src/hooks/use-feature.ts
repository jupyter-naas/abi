'use client';

import { isFeatureEnabled, type FeatureKey } from '@/lib/feature-access';
import { useWorkspaceStore } from '@/stores/workspace';

export function useFeature(feature: FeatureKey): boolean {
  const currentWorkspace = useWorkspaceStore((state) => state.getCurrentWorkspace());
  return isFeatureEnabled({
    feature,
    role: currentWorkspace?.currentUserRole,
    workspaceFlags: currentWorkspace?.featureFlags,
  });
}
