'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { SETTINGS_GROUPS, visibleSettingsGroups, workspaceOrganization } from '@/components/shell/settings-nav';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceResourcesStore } from '@/hooks/use-workspace-resources';
import { workspaceContainer } from '@/components/access/access-scope';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { useAnalyticsAccessStore } from '@/hooks/use-analytics-access';
import { analyticsScopeKey } from '@/components/analytics/scope';

export function SettingsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const pathname = usePathname();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const flags = useWorkspaceStore((s) => s.getCurrentWorkspace()?.featureFlags);
  // What a settings page has already read. Asking here starts the slow resources read
  // in front of Analytics and Access.
  const resources = useWorkspaceResourcesStore((s) =>
    currentWorkspaceId ? (s.byWorkspace[currentWorkspaceId]?.resources ?? null) : null
  );
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === s.currentWorkspaceId));
  const roleOpens = useFeature('settings.workspace');
  const basePath = getWorkspacePath(currentWorkspaceId, '/settings');
  // Access stays listed for an owner or admin until this answers, then follows IAM.
  const { access, loading: accessLoading } = useIamAccess(
    workspace ? workspaceContainer(workspaceOrganization(workspace), workspace.id) : undefined,
    undefined,
    { skip: !workspace }
  );
  // Analytics stays listed for that role until a settings page has read it.
  const analyticsKey = workspace ? analyticsScopeKey({ kind: 'workspace', workspaceId: workspace.id }) : null;
  const analyticsEntry = useAnalyticsAccessStore((s) => (analyticsKey ? s.entries[analyticsKey] : undefined));
  const analyticsKnown = analyticsEntry?.status === 'ready' || analyticsEntry?.status === 'error';
  // Only what the caller may use here (the features they hold, the module resources they may use).
  const groups = visibleSettingsGroups(resources, flags, SETTINGS_GROUPS, {
    access: workspace ? access : null,
    readsAnalytics: analyticsEntry?.access?.can_read === true,
    roleOpens,
    accessKnown: !!workspace && !accessLoading,
    analyticsKnown,
  });

  return (
    <CollapsibleSection
      id="settings"
      icon={<Settings size={18} />}
      label="Settings"
      description="Workspace configuration"
      href={basePath}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div className="space-y-0.5">
        {groups.map((group) => (
          <div key={group.label} className="space-y-0.5">
            <p className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {group.label}
            </p>
            {group.items.map((item) => {
              const fullHref = getWorkspacePath(currentWorkspaceId, item.href);
              const isActive = pathname === fullHref || pathname.startsWith(`${fullHref}/`) || pathname.endsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={fullHref}
                  className={cn(
                    'flex w-full items-center gap-1 px-2 py-1.5 settings-sidebar-list-row transition-colors',
                    isActive
                      ? 'bg-workspace-accent-15 text-workspace-accent'
                      : 'text-muted-foreground hover:bg-workspace-accent-10 hover:text-foreground'
                  )}
                >
                  <Icon size={14} className="flex-shrink-0" />
                  <span className="flex-1 truncate text-left">{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </div>
    </CollapsibleSection>
  );
}
