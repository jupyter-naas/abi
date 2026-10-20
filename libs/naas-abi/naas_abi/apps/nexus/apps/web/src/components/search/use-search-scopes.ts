'use client';

import { useCallback, useEffect, useMemo } from 'react';
import { isFeatureEnabled } from '@/lib/feature-access';
import { allowedWebEngines, availableScopes, isScopeOn, type SearchScope } from '@/lib/search-scopes';
import { useSearchStore } from '@/stores/search';
import { useSearchScopesStore } from '@/stores/search-scopes';
import { useSearchTopicsStore } from '@/stores/search-topics';
import { useWorkspaceStore } from '@/stores/workspace';

/** The scopes this workspace offers, with the user's on/off choice for each. */
export function useSearchScopes(workspaceId: string | null) {
  const workspace = useWorkspaceStore(state => state.getCurrentWorkspace());
  const { topics, disabledScopes, canEdit, loading, error, load } = useSearchTopicsStore();
  const overrides = useSearchScopesStore(state => state.overrides);
  const setScopeOn = useSearchScopesStore(state => state.setScopeOn);
  useEffect(() => { if (workspaceId) void load(workspaceId); }, [workspaceId, load]);

  const scopes = useMemo<SearchScope[]>(() => availableScopes(topics, feature => isFeatureEnabled({
    feature, role: workspace?.currentUserRole, workspaceFlags: workspace?.featureFlags,
  }), disabledScopes), [topics, workspace?.currentUserRole, workspace?.featureFlags, disabledScopes]);

  // The web engines this workspace allows; the legacy store queries only those.
  const allowedEngines = useMemo(() => allowedWebEngines(disabledScopes), [disabledScopes]);
  const setAllowedEngines = useSearchStore(state => state.setAllowedEngines);
  useEffect(() => { setAllowedEngines(allowedEngines); }, [allowedEngines, setAllowedEngines]);

  // Web has no switch of its own: it is on when one of its engines is.
  const webOn = useSearchStore(state => state.sources.some(s => s.enabled && allowedEngines.includes(s.id)));
  const isOn = useCallback(
    (scope: SearchScope) => (scope.kind === 'web' ? webOn : isScopeOn(scope, overrides)),
    [overrides, webOn],
  );
  return { scopes, isOn, setScopeOn, topics, allowedEngines, canEdit, loading, error };
}
