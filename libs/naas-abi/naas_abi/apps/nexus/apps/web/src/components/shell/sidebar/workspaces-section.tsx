'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, ChevronRight, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { groupWorkspaces, listWorkspaces } from '@/lib/workspace-picker';
import {
  isWorkspaceGroupExpanded,
  readWorkspaceGroupCollapse,
  writeWorkspaceGroupCollapsed,
  workspaceGroupKey,
} from '@/lib/workspace-group-collapse';
import { getWorkspaceHomePath } from '@/lib/feature-access';
import { markAppsSkipRestore } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';
import { useOrganizationStore } from '@/stores/organization';
import { useWorkspaceStore, type Workspace } from '@/stores/workspace';
import { WorkspaceMark, WorkspaceMarkFrame } from '../workspace-mark';
import { shellTokens } from '../tokens';

export function WorkspacesSection({ onPicked }: { onPicked?: () => void }) {
  const router = useRouter();
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const closeWorkspacesPanel = useWorkspaceStore((s) => s.closeWorkspacesPanel);
  const dismissWorkspacesPanel = useWorkspaceStore((s) => s.dismissWorkspacesPanel);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismissWorkspacesPanel();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [dismissWorkspacesPanel]);

  const listed = useMemo(() => listWorkspaces(workspaces, ''), [workspaces]);
  // Grouped by workspace group (Settings → General); no group shows under "Others".
  const grouped = useMemo(() => groupWorkspaces(listed), [listed]);

  const organizations = useOrganizationStore((s) => s.organizations);
  const currentOrgSlug = useOrganizationStore((s) => s.currentOrgSlug);
  const orgScope = useMemo(() => {
    const org = currentOrgSlug
      ? organizations.find((row) => row.slug === currentOrgSlug)
      : organizations[0];
    return org?.id ?? 'default';
  }, [organizations, currentOrgSlug]);

  const [collapsedByKey, setCollapsedByKey] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setCollapsedByKey(readWorkspaceGroupCollapse(orgScope));
  }, [orgScope]);

  const groupExpanded = useCallback(
    (group: string) => isWorkspaceGroupExpanded(group, collapsedByKey),
    [collapsedByKey],
  );

  const toggleGroup = useCallback(
    (group: string) => {
      const nextCollapsed = groupExpanded(group);
      const row = writeWorkspaceGroupCollapsed(orgScope, group, nextCollapsed);
      setCollapsedByKey(row);
    },
    [groupExpanded, orgScope],
  );

  const pick = (workspace: Workspace) => {
    if (workspace.id === currentWorkspaceId) {
      closeWorkspacesPanel();
      onPicked?.();
      return;
    }
    setActiveConversation(null);
    markAppsSkipRestore();
    setCurrentWorkspace(workspace.id);
    router.push(getWorkspaceHomePath(workspace.id));
    onPicked?.();
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 bg-background px-3 py-2">
        <span className="text-sm font-semibold">Workspaces</span>
        <button
          type="button"
          onClick={() => dismissWorkspacesPanel()}
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Close workspaces"
          title="Close workspaces"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto scrollbar-none px-1 pb-2">
        {listed.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-foreground">No workspaces</p>
        ) : (
          grouped.map(({ group, workspaces: items }) => {
            const expanded = groupExpanded(group);
            const panelId = `workspace-group-${workspaceGroupKey(group)}`;
            return (
              <section key={group} aria-label={group} className="flex flex-col gap-1">
                <button
                  type="button"
                  id={`${panelId}-label`}
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  onClick={() => toggleGroup(group)}
                  className={cn(
                    'flex w-full items-center gap-1 px-2 pt-2 text-left hover:text-foreground',
                    shellTokens.sidebar.sectionLabel,
                    'uppercase tracking-wide',
                  )}
                >
                  <ChevronRight
                    size={12}
                    className={cn('shrink-0 transition-transform', expanded && 'rotate-90')}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1 truncate">{group}</span>
                  <span className="shrink-0 tabular-nums opacity-70">{items.length}</span>
                </button>
                {expanded && (
                  <div id={panelId} role="region" aria-labelledby={`${panelId}-label`} className="flex flex-col gap-1">
                    {items.map((workspace) => (
                      <WorkspaceRow
                        key={workspace.id}
                        workspace={workspace}
                        current={workspace.id === currentWorkspaceId}
                        onPick={pick}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })
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
