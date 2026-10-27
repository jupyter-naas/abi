import { beforeEach, describe, expect, it } from 'vitest';

import { dropRetiredPanelSections, useWorkspaceStore, type SidebarSection } from './workspace';

describe('workspaces panel return section', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({
      activePanelSection: null,
      lastActivePanelSection: null,
      panelSectionBeforeWorkspaces: null,
    });
  });

  it('closing Workspaces restores the column it covered', () => {
    const { setActivePanelSection } = useWorkspaceStore.getState();
    setActivePanelSection('maps');
    setActivePanelSection('workspaces');
    expect(useWorkspaceStore.getState().activePanelSection).toBe('workspaces');

    useWorkspaceStore.getState().closeWorkspacesPanel();

    expect(useWorkspaceStore.getState().activePanelSection).toBe('maps');
  });

  it('closing Workspaces opened over no column closes the column', () => {
    useWorkspaceStore.getState().setActivePanelSection('chat');
    useWorkspaceStore.getState().setActivePanelSection(null);
    useWorkspaceStore.getState().setActivePanelSection('workspaces');

    useWorkspaceStore.getState().closeWorkspacesPanel();

    expect(useWorkspaceStore.getState().activePanelSection).toBeNull();
  });

  it('re-selecting Workspaces does not overwrite the return section', () => {
    const { setActivePanelSection } = useWorkspaceStore.getState();
    setActivePanelSection('files');
    setActivePanelSection('workspaces');
    setActivePanelSection('workspaces');

    useWorkspaceStore.getState().closeWorkspacesPanel();

    expect(useWorkspaceStore.getState().activePanelSection).toBe('files');
  });

  it('is a no-op when Workspaces is not open', () => {
    useWorkspaceStore.getState().setActivePanelSection('chat');

    useWorkspaceStore.getState().closeWorkspacesPanel();

    expect(useWorkspaceStore.getState().activePanelSection).toBe('chat');
  });
});

describe('dropRetiredPanelSections', () => {
  it('forgets a stored Events or Lab column, which the dock no longer has', () => {
    const stored = {
      expandedSections: ['chat', 'events', 'lab', 'files'],
      activePanelSection: 'events' as SidebarSection,
      lastActivePanelSection: 'lab' as SidebarSection,
    };

    dropRetiredPanelSections(stored);

    expect(stored).toEqual({
      expandedSections: ['chat', 'files'],
      activePanelSection: null,
      lastActivePanelSection: null,
    });
  });

  it('keeps a column the dock has, and never restores a transient one', () => {
    const stored = {
      expandedSections: ['maps'],
      activePanelSection: 'maps' as SidebarSection,
      lastActivePanelSection: 'workspaces' as SidebarSection,
    };

    dropRetiredPanelSections(stored);

    expect(stored.activePanelSection).toBe('maps');
    expect(stored.expandedSections).toEqual(['maps']);
    expect(stored.lastActivePanelSection).toBeNull();
  });
});
