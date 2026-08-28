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

export function recentWorkspaces<T extends NamedWorkspace>(
  workspaces: readonly T[],
  recentIds: readonly string[],
  currentId: string | null,
): T[] {
  const byId = new Map(workspaces.map((w) => [w.id, w]));
  const out: T[] = [];
  const seen = new Set<string>();
  for (const id of recentIds) {
    if (!id || id === currentId || seen.has(id)) continue;
    const hit = byId.get(id);
    if (!hit) continue;
    seen.add(id);
    out.push(hit);
  }
  return out;
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
