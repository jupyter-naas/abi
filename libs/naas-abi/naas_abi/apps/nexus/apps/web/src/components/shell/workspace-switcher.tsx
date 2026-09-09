'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { dockShowsLabels } from '@/lib/shell-columns';
import { WorkspaceMark, WorkspaceMarkFrame } from './workspace-mark';
import { WorkspacesSection } from './sidebar/workspaces-section';

/**
 * Workspace mark, docked at the top of the Sidebar. Clicking it opens a
 * flyout listing workspaces to switch to, anchored under the mark — not the
 * old mark-owned SectionPanel takeover, which read as a second sidebar.
 *
 * The flyout is portaled to `document.body` (like QuickOpen) rather than
 * absolutely positioned inline: Sidebar's `.glass` backdrop-filter makes it
 * its own stacking context, which trapped an inline flyout behind
 * SectionPanel/main whenever it overflowed the (often icon-only, ~56px)
 * dock width.
 */
export function WorkspaceSwitcher() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [listBox, setListBox] = useState<{ top: number; left: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const dockWidth = useWorkspaceStore((s) => s.dockWidth);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
  const labeled = dockShowsLabels(dockWidth);

  useEffect(() => {
    setMounted(true);
  }, []);

  useLayoutEffect(() => {
    if (!open || !wrapRef.current) {
      setListBox(null);
      return;
    }
    const rect = wrapRef.current.getBoundingClientRect();
    setListBox({ top: rect.bottom + 4, left: rect.left });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (wrapRef.current?.contains(target) || listRef.current?.contains(target)) return;
      setOpen(false);
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
      className="relative flex h-14 w-full shrink-0 items-center justify-center border-b border-border/50"
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

      {open && mounted
        ? createPortal(
            <div
              id="workspace-switcher-list"
              ref={listRef}
              role="listbox"
              className="fixed z-[260] max-h-[min(28rem,70vh)] w-72 overflow-y-auto bg-popover p-2 shadow-xl"
              style={{ top: listBox?.top ?? 56, left: listBox?.left ?? 0 }}
            >
              <WorkspacesSection onPicked={() => setOpen(false)} />
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
