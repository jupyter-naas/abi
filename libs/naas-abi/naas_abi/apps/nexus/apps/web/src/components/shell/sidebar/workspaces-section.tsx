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
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);

  const listed = useMemo(() => listWorkspaces(workspaces, query), [workspaces, query]);

  const pick = (workspace: Workspace) => {
    if (workspace.id === currentWorkspaceId) {
      setActivePanelSection(null);
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
    <div className="flex flex-col gap-2">
      <label className="relative block px-1">
        <Search
          size={14}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search workspaces"
          autoFocus
          className="w-full border border-border/60 bg-background py-1.5 pl-8 pr-2 text-sm outline-none focus:border-workspace-accent"
        />
      </label>

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
