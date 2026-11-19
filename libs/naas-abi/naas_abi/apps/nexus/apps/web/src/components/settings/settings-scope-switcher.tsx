'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown, Loader2, type LucideIcon } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { visiblePlatformSettingsGroups } from '@/app/settings/lib/nav';
import { useAuthStore } from '@/stores/auth';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { settingsScopeFromPathname } from '@/lib/settings-scope-path';
import { buildSettingsScopeMenuEntries, opensAnotherPage } from './settings-scope-list';
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
  const accountName = useAuthStore((s) => s.user?.name);
  const platformSettings = usePlatformSettingsAccess();
  const showPlatform =
    platformSettings.status === 'ready' &&
    visiblePlatformSettingsGroups(platformSettings.actions).length > 0;

  // Shared with the avatar menu: one read per user, kept across scope switches.
  const { orgs: organizations } = useOpenableOrganizations();

  // The entry followed, until its page replaces this one: a scope's first open can
  // take seconds (``next dev`` compiles it), and a click must not look like a no-op.
  const [followed, setFollowed] = useState<{ href: string; from: string } | null>(null);
  const pendingHref = followed && followed.from === pathname ? followed.href : null;

  if (!currentScope || currentScope.kind === 'workspace') return null;

  const entries = buildSettingsScopeMenuEntries({
    currentScope,
    showPlatform,
    platformActions: platformSettings.actions,
    organizations: organizations.map((o) => ({ id: o.id, name: o.name })),
    accountName,
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
          aria-busy={pendingHref ? true : undefined}
        >
          <span className="settings-scope-switcher-title">{title}</span>
          {pendingHref ? (
            <Loader2 size={16} className="settings-scope-switcher-chevron animate-spin" aria-hidden />
          ) : (
            <ChevronDown size={16} className="settings-scope-switcher-chevron" aria-hidden />
          )}
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
                      aria-busy={pendingHref === entry.href ? true : undefined}
                      onClick={(event) => {
                        // A new tab or window leaves this page where it is.
                        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
                          return;
                        }
                        if (pathname && opensAnotherPage(entry.href, pathname)) {
                          setFollowed({ href: entry.href, from: pathname });
                        }
                      }}
                    >
                      <span className="settings-scope-switcher-check" aria-hidden>
                        {pendingHref === entry.href ? (
                          <Loader2 size={16} className="animate-spin" />
                        ) : entry.current ? (
                          <Check size={16} />
                        ) : null}
                      </span>
                      <span className="min-w-0 truncate">{entry.label}</span>
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