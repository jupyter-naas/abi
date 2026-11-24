'use client';

import { useMemo, useState } from 'react';
import { Check, Search } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  groupByOrganization,
  listWorkspaces,
  OTHERS_GROUP,
  spansOrganizations,
  type OrganizationSection,
  type WorkspaceGroup,
} from '@/lib/workspace-picker';
import { getWorkspaceHomePath } from '@/lib/feature-access';
import { markAppsSkipRestore } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';
import { useWorkspaceStore, type Workspace } from '@/stores/workspace';
import { WorkspaceMark, WorkspaceMarkFrame } from '../workspace-mark';
import { shellTokens } from '../tokens';

export function WorkspacesSection({ onPicked }: { onPicked?: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const closeWorkspacesPanel = useWorkspaceStore((s) => s.closeWorkspacesPanel);

  const listed = useMemo(() => listWorkspaces(workspaces, query), [workspaces, query]);
  const currentOrganizationId = workspaces.find((w) => w.id === currentWorkspaceId)?.organizationId;
  // Grouped by organization, then by workspace group (Settings → General; no group
  // shows under "Others"). The organization headings show only when the person's
  // workspaces span more than one organization (personal ones counting as one).
  const showOrganizations = useMemo(() => spansOrganizations(workspaces), [workspaces]);
  const sections = useMemo(
    () => groupByOrganization(listed, currentOrganizationId),
    [listed, currentOrganizationId],
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
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background px-3 py-2">
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

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto scrollbar-none">
        {listed.length === 0 ? (
          <p className="px-2 py-2 text-xs text-muted-foreground">No workspaces match</p>
        ) : showOrganizations ? (
          sections.map((section) => (
            <OrganizationBlock
              key={section.organizationId ?? 'personal'}
              section={section}
              logoUrl={
                section.organizationId
                  ? workspaces.find((w) => w.organizationId === section.organizationId)
                      ?.organizationLogoUrl
                  : undefined
              }
              currentWorkspaceId={currentWorkspaceId}
              onPick={pick}
            />
          ))
        ) : (
          sections
            .flatMap((section) => section.groups)
            .map((group) => (
              <GroupBlock
                key={group.group}
                group={group}
                currentWorkspaceId={currentWorkspaceId}
                onPick={pick}
              />
            ))
        )}
      </div>
    </div>
  );
}

function OrganizationBlock({
  section,
  logoUrl,
  currentWorkspaceId,
  onPick,
}: {
  section: OrganizationSection<Workspace>;
  logoUrl?: string;
  currentWorkspaceId: string | null;
  onPick: (workspace: Workspace) => void;
}) {
  const count = section.groups.reduce((total, group) => total + group.workspaces.length, 0);
  // An organization whose workspaces have no group lists them without an "Others" subheading.
  const flat = section.groups.length === 1 && section.groups[0].group === OTHERS_GROUP;
  return (
    <section aria-label={section.name} className="flex flex-col gap-1 border-b border-border/50 pb-2 last:border-b-0">
      <h2 className="flex items-center gap-2 px-2 pt-2 text-xs font-semibold text-foreground">
        {section.organizationId ? (
          <WorkspaceMarkFrame
            backgroundColor={logoUrl ? undefined : '#64748b'}
            className="h-5 w-5"
          >
            <WorkspaceMark
              name={section.name}
              logoUrl={logoUrl}
              letterClassName="text-[10px] text-white"
            />
          </WorkspaceMarkFrame>
        ) : null}
        <span className="min-w-0 flex-1 truncate">{section.name}</span>
        <span className="tabular-nums text-[11px] font-normal text-muted-foreground">{count}</span>
      </h2>
      {flat
        ? section.groups[0].workspaces.map((workspace) => (
            <WorkspaceRow
              key={workspace.id}
              workspace={workspace}
              current={workspace.id === currentWorkspaceId}
              onPick={onPick}
            />
          ))
        : section.groups.map((group) => (
            <GroupBlock
              key={group.group}
              group={group}
              currentWorkspaceId={currentWorkspaceId}
              onPick={onPick}
            />
          ))}
    </section>
  );
}

function GroupBlock({
  group,
  currentWorkspaceId,
  onPick,
}: {
  group: WorkspaceGroup<Workspace>;
  currentWorkspaceId: string | null;
  onPick: (workspace: Workspace) => void;
}) {
  return (
    <section aria-label={group.group} className="flex flex-col gap-1">
      <h3 className="px-2 pt-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {group.group}
        <span className="ml-1.5 tabular-nums opacity-70">{group.workspaces.length}</span>
      </h3>
      {group.workspaces.map((workspace) => (
        <WorkspaceRow
          key={workspace.id}
          workspace={workspace}
          current={workspace.id === currentWorkspaceId}
          onPick={onPick}
        />
      ))}
    </section>
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
      aria-current={current ? 'true' : undefined}
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
