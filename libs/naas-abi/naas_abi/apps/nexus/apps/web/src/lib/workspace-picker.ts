export type NamedWorkspace = {
  id: string;
  name: string;
};

export function filterWorkspaces<T extends NamedWorkspace>(
  workspaces: readonly T[],
  query: string,
): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...workspaces];
  return workspaces.filter((w) => w.name.toLowerCase().includes(q));
}

/** One alphabetical catalog. Current is highlighted in the UI; it does not change order. */
export function listWorkspaces<T extends NamedWorkspace>(
  workspaces: readonly T[],
  query: string,
): T[] {
  return filterWorkspaces(workspaces, query).sort((a, b) => a.name.localeCompare(b.name));
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
