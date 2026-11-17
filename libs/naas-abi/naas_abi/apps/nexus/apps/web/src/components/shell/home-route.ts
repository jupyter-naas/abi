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

/**
 * What the dock should do with the feature column when the path changes.
 * `'keep'` leaves the stored column: a refresh must not reopen one the user
 * closed. Later navigations open the section of the new path.
 */
export type PanelFromPathChange = 'keep' | SidebarSection | null;

export function panelFromPathChange(input: {
  previousPath: string | null;
  pathname: string;
  urlSection: SidebarSection | null;
  keepPanelClosed: boolean;
  currentPanel: SidebarSection | null;
}): PanelFromPathChange {
  const { previousPath, pathname, urlSection, keepPanelClosed, currentPanel } = input;
  if (previousPath === pathname) return 'keep';
  if (keepPanelClosed) return null;
  if (pathname.endsWith('/settings/infrastructure')) {
    return previousPath === null ? 'keep' : 'infrastructure';
  }
  if (urlSection === null) {
    if (pathname.includes('/admin/')) return null;
    return 'keep';
  }
  if (urlSection === 'home') {
    return currentPanel === 'workspaces' ? 'keep' : null;
  }
  if (previousPath === null) return 'keep';
  return urlSection;
}
