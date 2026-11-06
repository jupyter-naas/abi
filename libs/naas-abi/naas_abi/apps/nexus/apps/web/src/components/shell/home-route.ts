import type { SidebarSection } from '@/stores/workspace';

/** True on a workspace's Home desk (`/workspace/<id>/home`). */
export function isWorkspaceHome(pathname: string | null | undefined, workspaceId: string | null): boolean {
  if (!pathname || !workspaceId) return false;
  const home = `/workspace/${workspaceId}/home`;
  return pathname === home || pathname.startsWith(`${home}/`);
}

/**
 * The section column a page shows. Home is a desk, not a column: whatever
 * section the store still holds (a reload, the top bar toggle, a section
 * opened before navigating), Home shows none. Only the Workspaces panel the
 * workspace mark opens may sit over it.
 */
export function panelSectionOnPage(
  section: SidebarSection | null,
  pathname: string | null | undefined,
  workspaceId: string | null,
): SidebarSection | null {
  if (section !== 'workspaces' && isWorkspaceHome(pathname, workspaceId)) return null;
  return section;
}
