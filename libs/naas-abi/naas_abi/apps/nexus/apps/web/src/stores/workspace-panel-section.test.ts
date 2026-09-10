import { beforeEach, describe, expect, it } from 'vitest';

import { useWorkspaceStore } from './workspace';

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
    setActivePanelSection('events');
    setActivePanelSection('workspaces');
    expect(useWorkspaceStore.getState().activePanelSection).toBe('workspaces');

    useWorkspaceStore.getState().closeWorkspacesPanel();

    expect(useWorkspaceStore.getState().activePanelSection).toBe('events');
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
