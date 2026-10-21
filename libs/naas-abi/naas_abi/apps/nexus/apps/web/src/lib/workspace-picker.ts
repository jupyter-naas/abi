export type NamedWorkspace = {
  id: string;
  name: string;
  /** Workspace group (Settings → General); empty means "Others". */
  group?: string | null;
};

export const OTHERS_GROUP = 'Others';

export function filterWorkspaces<T extends NamedWorkspace>(
  workspaces: readonly T[],
  query: string,
): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...workspaces];
  return workspaces.filter(
    (w) => w.name.toLowerCase().includes(q) || (w.group ?? '').toLowerCase().includes(q)
  );
}

/** One alphabetical catalog. Current is highlighted in the UI; it does not change order. */
export function listWorkspaces<T extends NamedWorkspace>(
  workspaces: readonly T[],
  query: string,
): T[] {
  return filterWorkspaces(workspaces, query).sort((a, b) => a.name.localeCompare(b.name));
}

export interface WorkspaceGroup<T> {
  group: string;
  workspaces: T[];
}

/**
 * Workspaces by group: named groups alphabetically, then "Others" (no group).
 * Each group keeps the alphabetical order of ``listWorkspaces``.
 */
export function groupWorkspaces<T extends NamedWorkspace>(
  workspaces: readonly T[],
): WorkspaceGroup<T>[] {
  const byGroup = new Map<string, T[]>();
  for (const workspace of workspaces) {
    const group = workspace.group?.trim() || OTHERS_GROUP;
    byGroup.set(group, [...(byGroup.get(group) ?? []), workspace]);
  }
  return [...byGroup.entries()]
    .sort(([a], [b]) =>
      a === OTHERS_GROUP ? 1 : b === OTHERS_GROUP ? -1 : a.localeCompare(b)
    )
    .map(([group, items]) => ({ group, workspaces: items }));
}

export function pushRecentWorkspaceId(
  recentIds: readonly string[],
  previousId: string | null,
  nextId: string,
  limit = 8,
): string[] {
  const next = recentIds.filter((id) => id !== nextId && id !== previousId);
  if (previousId && previousId !== nextId) next.unshift(previousId);
  return next.slice(0, limit);
}
