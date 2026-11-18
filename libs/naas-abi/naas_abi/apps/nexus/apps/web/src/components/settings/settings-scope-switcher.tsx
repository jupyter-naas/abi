'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown, ExternalLink, type LucideIcon } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { visiblePlatformSettingsGroups } from '@/app/settings/lib/nav';
import { useWorkspaceStore } from '@/stores/workspace';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { settingsScopeFromPathname } from '@/lib/settings-scope-path';
import { buildSettingsScopeMenuEntries } from './settings-scope-list';
import './settings-scope-switcher.css';

export function SettingsScopeSwitcher({
  title,
  icon: Icon,
}: {
  title: string;
  icon?: LucideIcon;
}) {
  const pathname = usePathname();
  const currentScope = useMemo(() => settingsScopeFromPathname(pathname), [pathname]);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
  const platformSettings = usePlatformSettingsAccess();
  const showPlatform =
    platformSettings.status === 'ready' &&
    visiblePlatformSettingsGroups(platformSettings.actions).length > 0;

  // Shared with the avatar menu: one read per user, kept across scope switches.
  const { orgs: organizations } = useOpenableOrganizations();

  if (!currentScope || currentScope.kind === 'workspace') return null;

  const entries = buildSettingsScopeMenuEntries({
    currentScope,
    showPlatform,
    platformActions: platformSettings.actions,
    organizations: organizations.map((o) => ({ id: o.id, name: o.name })),
    workspace: currentWorkspace ? { id: currentWorkspace.id, name: currentWorkspace.name } : null,
  });

  if (entries.length <= 1) {
    return (
      <div className="org-settings-layout-header-meta">
        {Icon && <Icon size={16} className="org-settings-layout-header-icon" />}
        <h1 className="org-settings-layout-header-title">{title}</h1>
      </div>
    );
  }

  return (
    <div className="org-settings-layout-header-meta min-w-0">
      {Icon && <Icon size={16} className="org-settings-layout-header-icon shrink-0" />}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger
          className="settings-scope-switcher-trigger"
          aria-label="Switch settings scope"
        >
          <span className="settings-scope-switcher-title">{title}</span>
          <ChevronDown size={16} className="settings-scope-switcher-chevron" aria-hidden />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            className="settings-scope-switcher-content"
            align="start"
            sideOffset={4}
            collisionPadding={8}
          >
            <nav aria-label="Settings scopes">
              {entries.map((entry) => {
                if (entry.type === 'separator') {
                  return <div key={entry.id} className="settings-scope-switcher-separator" role="presentation" />;
                }
                return (
                  <DropdownMenu.Item key={entry.id} asChild onSelect={(e) => e.preventDefault()}>
                    <Link
                      href={entry.href}
                      className="settings-scope-switcher-link"
                      aria-current={entry.current ? 'page' : undefined}
                    >
                      <span className="settings-scope-switcher-check" aria-hidden>
                        {entry.current ? <Check size={16} /> : null}
                      </span>
                      <span className="min-w-0 truncate">{entry.label}</span>
                      {entry.external ? (
                        <ExternalLink size={14} className="settings-scope-switcher-external" aria-hidden />
                      ) : null}
                    </Link>
                  </DropdownMenu.Item>
                );
              })}
            </nav>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  );
}