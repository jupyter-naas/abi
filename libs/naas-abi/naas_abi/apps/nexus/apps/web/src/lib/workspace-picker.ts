export type NamedWorkspace = {
  id: string;
  name: string;
  /** Workspace group (Settings → General); empty means "Others". */
  group?: string | null;
  /** The organization it belongs to; none for a personal workspace. */
  organizationId?: string | null;
  organizationName?: string | null;
};

export const OTHERS_GROUP = 'Others';
/** Heading of the workspaces that belong to no organization. */
export const PERSONAL_ORGANIZATION = 'Personal';

export function filterWorkspaces<T extends NamedWorkspace>(
  workspaces: readonly T[],
  query: string,
): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...workspaces];
  return workspaces.filter(
    (w) =>
      w.name.toLowerCase().includes(q)
      || (w.group ?? '').toLowerCase().includes(q)
      || (w.organizationName ?? '').toLowerCase().includes(q)
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

export interface OrganizationSection<T> {
  /** The organization's id; null for the workspaces in none ("Personal"). */
  organizationId: string | null;
  /** Its name, or ``PERSONAL_ORGANIZATION``. */
  name: string;
  /** Its workspaces, by workspace group (``groupWorkspaces``). */
  groups: WorkspaceGroup<T>[];
}

/**
 * Whether the list needs organization headings: only when the user's workspaces
 * belong to more than one organization (personal workspaces counting as one).
 * Decided on every workspace, not a search's matches, so headings do not come
 * and go while typing.
 */
export function spansOrganizations(workspaces: readonly NamedWorkspace[]): boolean {
  return new Set(workspaces.map((w) => w.organizationId || null)).size > 1;
}

/**
 * Whether the list needs group headings: only when some workspace has a group.
 * Without one, an "Others" heading over every workspace says nothing. Decided
 * on every workspace, like ``spansOrganizations``.
 */
export function hasWorkspaceGroups(workspaces: readonly NamedWorkspace[]): boolean {
  return workspaces.some((w) => !!w.group?.trim());
}

/**
 * Workspaces by organization, then by workspace group: two organizations' groups of
 * the same name stay apart. The current workspace's organization comes first, the
 * others alphabetically, then "Personal" (no organization). Each organization's
 * workspaces keep the order of ``listWorkspaces``.
 */
export function groupByOrganization<T extends NamedWorkspace>(
  workspaces: readonly T[],
  currentOrganizationId?: string | null,
): OrganizationSection<T>[] {
  const byOrganization = new Map<string | null, T[]>();
  for (const workspace of workspaces) {
    const key = workspace.organizationId || null;
    byOrganization.set(key, [...(byOrganization.get(key) ?? []), workspace]);
  }
  const current = currentOrganizationId || null;
  const rank = (id: string | null) => (id === null ? 2 : id === current ? 0 : 1);
  return [...byOrganization.entries()]
    .map(([organizationId, items]) => ({
      organizationId,
      name:
        organizationId === null
          ? PERSONAL_ORGANIZATION
          : items.find((w) => w.organizationName?.trim())?.organizationName?.trim()
            || organizationId,
      groups: groupWorkspaces(items),
    }))
    .sort(
      (a, b) =>
        rank(a.organizationId) - rank(b.organizationId)
        || a.name.localeCompare(b.name)
        || (a.organizationId ?? '').localeCompare(b.organizationId ?? '')
    );
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
