'use client';

import { useCallback, useEffect, useMemo } from 'react';
import { isFeatureEnabled } from '@/lib/feature-access';
import { availableScopes, isScopeOn, type SearchScope } from '@/lib/search-scopes';
import { useSearchStore, WEB_ENGINE_IDS } from '@/stores/search';
import { useSearchScopesStore } from '@/stores/search-scopes';
import { useSearchTopicsStore } from '@/stores/search-topics';
import { useWorkspaceStore } from '@/stores/workspace';

/** The scopes this workspace offers, with the user's on/off choice for each. */
export function useSearchScopes(workspaceId: string | null) {
  const workspace = useWorkspaceStore(state => state.getCurrentWorkspace());
  const { topics, canEdit, loading, error, load } = useSearchTopicsStore();
  const overrides = useSearchScopesStore(state => state.overrides);
  const setScopeOn = useSearchScopesStore(state => state.setScopeOn);
  useEffect(() => { if (workspaceId) void load(workspaceId); }, [workspaceId, load]);

  const scopes = useMemo<SearchScope[]>(() => availableScopes(topics, feature => isFeatureEnabled({
    feature, role: workspace?.currentUserRole, workspaceFlags: workspace?.featureFlags,
  })), [topics, workspace?.currentUserRole, workspace?.featureFlags]);

  // Web has no switch of its own: it is on when one of its engines is.
  const webOn = useSearchStore(state => state.sources.some(s => s.enabled && WEB_ENGINE_IDS.includes(s.id)));
  const isOn = useCallback(
    (scope: SearchScope) => (scope.kind === 'web' ? webOn : isScopeOn(scope, overrides)),
    [overrides, webOn],
  );
  return { scopes, isOn, setScopeOn, topics, canEdit, loading, error };
}
