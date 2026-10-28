'use client';

import {
  useDatabaseViews,
  type DatabaseViewsApi,
  type DatabaseViewsOptions,
} from '@/components/database-view/use-database-views';
import {
  DEFAULT_VISIBLE,
  PROPERTIES,
  VIEW_TYPE_LABELS,
  type PropertyKey,
  type ViewType,
} from './types';

/**
 * App views live in localStorage, per workspace (see `useDatabaseViews`).
 * The storage key predates the shared hook and is kept so saved views survive.
 */
export const APP_VIEWS: DatabaseViewsOptions<PropertyKey, ViewType> = {
  storagePrefix: 'nexus.apps.views',
  viewTypeLabels: VIEW_TYPE_LABELS,
  propertyKeys: PROPERTIES.map((p) => p.key),
  titleKey: 'name',
  createView: (type, name) => ({
    name,
    type,
    visible: [...DEFAULT_VISIBLE[type]],
    filters: [],
    sort: null,
    groupBy: type === 'board' ? 'module' : null,
  }),
  defaultViews: () => [APP_VIEWS.createView('gallery', 'Gallery')],
};

export type AppViewsApi = DatabaseViewsApi<PropertyKey, ViewType>;

export function useAppViews(workspaceId: string | null): AppViewsApi {
  return useDatabaseViews(workspaceId, APP_VIEWS);
}
