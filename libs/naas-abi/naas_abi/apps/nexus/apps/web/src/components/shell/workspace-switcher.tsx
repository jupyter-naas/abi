'use client';

import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { dockShowsLabels } from '@/lib/shell-columns';
import { WorkspaceMark, WorkspaceMarkFrame } from './workspace-mark';

/**
 * Workspace mark at the top of the dock. Clicking it opens the Workspaces
 * list in the left feature column (SectionPanel), same chrome as Chat,
 * Events, and Files.
 */
export function WorkspaceSwitcher() {
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const dockWidth = useWorkspaceStore((s) => s.dockWidth);
  const activePanelSection = useWorkspaceStore((s) => s.activePanelSection);
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
  const labeled = dockShowsLabels(dockWidth);
  const open = activePanelSection === 'workspaces';

  return (
    <div className="relative flex h-14 w-full shrink-0 items-center justify-center border-b border-border/50">
      <button
        type="button"
        onClick={() => setActivePanelSection(open ? null : 'workspaces')}
        aria-label="Workspaces"
        aria-expanded={open}
        title="Workspaces"
        className={cn(
          'flex h-full w-full items-center outline-none focus-visible:ring-0',
          labeled ? 'gap-3 px-3' : 'justify-center',
        )}
      >
        <WorkspaceMarkFrame
          backgroundColor={
            currentWorkspace?.theme?.logoUrl ? undefined : (currentWorkspace?.theme?.primaryColor || '#22c55e')
          }
          className="h-10 w-10"
        >
          <WorkspaceMark
            name={currentWorkspace?.name}
            icon={currentWorkspace?.icon}
            logoUrl={currentWorkspace?.theme?.logoUrl}
            logoEmoji={currentWorkspace?.theme?.logoEmoji}
            letterClassName="text-sm font-bold text-white"
          />
        </WorkspaceMarkFrame>
        {labeled && (
          <span className="truncate text-sm font-medium text-foreground">
            {currentWorkspace?.name || 'NEXUS'}
          </span>
        )}
      </button>
    </div>
  );
}
