import { OTHERS_GROUP } from '@/lib/workspace-picker';

export const WORKSPACE_GROUP_COLLAPSE_STORAGE_KEY = 'nexus-workspace-picker-group-collapse';

export type WorkspaceGroupCollapseStore = Record<string, Record<string, boolean>>;

export function workspaceGroupKey(group: string): string {
  return group.trim().toLowerCase();
}

export function isOthersWorkspaceGroup(group: string): boolean {
  return workspaceGroupKey(group) === workspaceGroupKey(OTHERS_GROUP);
}

/** True when the group should start collapsed (rows hidden) with no saved preference. */
export function defaultWorkspaceGroupCollapsed(group: string): boolean {
  return isOthersWorkspaceGroup(group);
}

export function isWorkspaceGroupExpanded(
  group: string,
  collapsedByKey: Readonly<Record<string, boolean>>,
  options?: { forceExpanded?: boolean },
): boolean {
  if (options?.forceExpanded) return true;
  const key = workspaceGroupKey(group);
  if (key in collapsedByKey) return !collapsedByKey[key];
  return !defaultWorkspaceGroupCollapsed(group);
}

type LegacyStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function readStore(storage: LegacyStorage): WorkspaceGroupCollapseStore {
  try {
    const parsed: unknown = JSON.parse(storage.getItem(WORKSPACE_GROUP_COLLAPSE_STORAGE_KEY) ?? '{}');
    if (!parsed || typeof parsed !== 'object') return {};
    const out: WorkspaceGroupCollapseStore = {};
    for (const [orgScope, groups] of Object.entries(parsed as Record<string, unknown>)) {
      if (!groups || typeof groups !== 'object') continue;
      const row: Record<string, boolean> = {};
      for (const [groupKey, collapsed] of Object.entries(groups as Record<string, unknown>)) {
        if (typeof collapsed === 'boolean') row[groupKey] = collapsed;
      }
      if (Object.keys(row).length) out[orgScope] = row;
    }
    return out;
  } catch {
    return {};
  }
}

function writeStore(storage: LegacyStorage, store: WorkspaceGroupCollapseStore) {
  if (Object.keys(store).length === 0) storage.removeItem(WORKSPACE_GROUP_COLLAPSE_STORAGE_KEY);
  else storage.setItem(WORKSPACE_GROUP_COLLAPSE_STORAGE_KEY, JSON.stringify(store));
}

export function readWorkspaceGroupCollapse(
  orgScope: string,
  storage: LegacyStorage | undefined = typeof window === 'undefined' ? undefined : window.localStorage,
): Record<string, boolean> {
  if (!storage || !orgScope) return {};
  const store = readStore(storage);
  return { ...(store[orgScope] ?? {}) };
}

export function writeWorkspaceGroupCollapsed(
  orgScope: string,
  group: string,
  collapsed: boolean,
  storage: LegacyStorage | undefined = typeof window === 'undefined' ? undefined : window.localStorage,
): Record<string, boolean> {
  if (!storage || !orgScope) return {};
  const store = readStore(storage);
  const key = workspaceGroupKey(group);
  const orgRow = { ...(store[orgScope] ?? {}), [key]: collapsed };
  store[orgScope] = orgRow;
  writeStore(storage, store);
  return orgRow;
}
