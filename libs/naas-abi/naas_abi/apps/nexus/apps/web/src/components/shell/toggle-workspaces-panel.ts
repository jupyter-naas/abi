import { useWorkspaceStore } from '@/stores/workspace';

/**
 * What the workspace mark at the top of the dock does: open the Workspaces
 * column, or close it and put back the column it covered.
 */
export function toggleWorkspacesPanel(): void {
  const { activePanelSection, closeWorkspacesPanel, setActivePanelSection } =
    useWorkspaceStore.getState();
  if (activePanelSection === 'workspaces') closeWorkspacesPanel();
  else setActivePanelSection('workspaces');
}
