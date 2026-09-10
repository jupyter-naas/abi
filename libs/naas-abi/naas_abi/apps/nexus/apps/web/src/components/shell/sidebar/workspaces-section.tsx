'use client';

import { useMemo, useState } from 'react';
import { Check, Search } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { listWorkspaces } from '@/lib/workspace-picker';
import { getWorkspaceSwitchPath } from '@/lib/feature-access';
import { markAppsSkipRestore } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';
import { useWorkspaceStore, type Workspace } from '@/stores/workspace';
import { WorkspaceMark, WorkspaceMarkFrame } from '../workspace-mark';
import { shellTokens } from '../tokens';

export function WorkspacesSection({ onPicked }: { onPicked?: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const [query, setQuery] = useState('');
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const closeWorkspacesPanel = useWorkspaceStore((s) => s.closeWorkspacesPanel);

  const listed = useMemo(() => listWorkspaces(workspaces, query), [workspaces, query]);

  const pick = (workspace: Workspace) => {
    if (workspace.id === currentWorkspaceId) {
      closeWorkspacesPanel();
      onPicked?.();
      return;
    }
    setActiveConversation(null);
    markAppsSkipRestore();
    setCurrentWorkspace(workspace.id);
    router.push(
      getWorkspaceSwitchPath({
        pathname,
        targetWorkspaceId: workspace.id,
        role: workspace.currentUserRole,
        workspaceFlags: workspace.featureFlags,
      }),
    );
    onPicked?.();
  };

  return (
    <div className="flex flex-col">
      {/* No gap between this and the list below: a flex gap is empty flow
          space that isn't part of the sticky row's own box, so a scrolled
          row's label would still be visible passing through it. The search
          row owns its full covered area (padding, not gap) instead. */}
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-background px-3 py-2">
        <Search size={14} className="shrink-0 opacity-70 text-muted-foreground" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search workspaces"
          autoFocus
          className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none focus-visible:ring-0 placeholder:text-muted-foreground"
          aria-label="Search workspaces"
        />
      </div>

      <div className="flex flex-col gap-2">
        {listed.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-foreground">No workspaces match</p>
        ) : (
          listed.map((workspace) => (
            <WorkspaceRow
              key={workspace.id}
              workspace={workspace}
              current={workspace.id === currentWorkspaceId}
              onPick={pick}
            />
          ))
        )}
      </div>
    </div>
  );
}

function WorkspaceRow({
  workspace,
  current,
  onPick,
}: {
  workspace: Workspace;
  current: boolean;
  onPick: (workspace: Workspace) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onPick(workspace)}
      className={cn(
        'flex w-full items-center gap-3 py-1.5 pl-2 pr-4 text-left text-sm transition-colors',
        shellTokens.sidebar.listRow,
        'hover:bg-workspace-accent-10',
        current && 'bg-workspace-accent-5',
      )}
    >
      <WorkspaceMarkFrame
        backgroundColor={
          workspace.theme?.logoUrl ? undefined : (workspace.theme?.primaryColor || '#22c55e')
        }
        className="h-6 w-6"
      >
        <WorkspaceMark
          name={workspace.name}
          icon={workspace.icon}
          logoUrl={workspace.theme?.logoUrl}
          logoEmoji={workspace.theme?.logoEmoji}
          letterClassName="text-xs text-white"
        />
      </WorkspaceMarkFrame>
      <span className="min-w-0 flex-1 truncate font-medium">{workspace.name}</span>
      {current && <Check size={14} className="flex-shrink-0 text-workspace-accent" />}
    </button>
  );
}
