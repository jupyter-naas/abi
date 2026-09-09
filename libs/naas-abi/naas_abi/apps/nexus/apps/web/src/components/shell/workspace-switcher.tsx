'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { dockShowsLabels } from '@/lib/shell-columns';
import { WorkspaceMark, WorkspaceMarkFrame } from './workspace-mark';
import { WorkspacesSection } from './sidebar/workspaces-section';

/**
 * Workspace mark, docked at the left of TopNav with the same width as the
 * dock below it. Clicking it opens a flyout listing workspaces to switch
 * to, anchored under the mark — not the old mark-owned SectionPanel
 * takeover, which read as a second sidebar.
 */
export function WorkspaceSwitcher() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const dockWidth = useWorkspaceStore((s) => s.dockWidth);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
  const labeled = dockShowsLabels(dockWidth);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div
      ref={wrapRef}
      className="relative flex h-full shrink-0 items-stretch"
      style={{ width: dockWidth }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Workspaces"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls="workspace-switcher-list"
        title="Workspaces"
        className={cn(
          'flex h-full w-full items-center outline-none focus-visible:ring-0',
          labeled ? 'gap-2 px-3' : 'justify-center',
        )}
      >
        <WorkspaceMarkFrame
          backgroundColor={
            currentWorkspace?.theme?.logoUrl ? undefined : (currentWorkspace?.theme?.primaryColor || '#22c55e')
          }
          className="h-6 w-6"
        >
          <WorkspaceMark
            name={currentWorkspace?.name}
            icon={currentWorkspace?.icon}
            logoUrl={currentWorkspace?.theme?.logoUrl}
            logoEmoji={currentWorkspace?.theme?.logoEmoji}
            letterClassName="text-xs font-bold text-white"
          />
        </WorkspaceMarkFrame>
        {labeled && (
          <span className="truncate text-sm font-medium text-foreground">
            {currentWorkspace?.name || 'NEXUS'}
          </span>
        )}
      </button>

      {open && (
        <div
          id="workspace-switcher-list"
          role="listbox"
          className="absolute left-0 top-full z-[260] max-h-[min(28rem,70vh)] w-72 overflow-y-auto bg-popover p-2 shadow-xl"
        >
          <WorkspacesSection onPicked={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}
