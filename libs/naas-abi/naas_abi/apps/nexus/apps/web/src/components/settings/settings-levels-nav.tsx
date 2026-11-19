'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import type { OrgSettingsNavItem } from '@/app/organizations/[orgId]/settings/lib/nav';
import { useDevRouteWarmup } from '@/hooks/use-dev-route-warmup';
import { useSettingsLevels } from '@/hooks/use-settings-levels';
import { activeSettingsHref } from './settings-levels';
import { SettingsLayoutNav } from './settings-layout-nav';
import { SettingsNavItem } from './settings-shell';

/** The column of Settings: every level the caller may open, the page's link marked. */
export function SettingsLevelsNav({
  mobileList = false,
  organization,
}: {
  /** The phone's list of Settings, full width. */
  mobileList?: boolean;
  /** The organization an organization's settings page has read (see useSettingsLevels). */
  organization?: { id: string; items: OrgSettingsNavItem[] };
}) {
  const pathname = usePathname() ?? '';
  const levels = useSettingsLevels({ organization });
  const active = activeSettingsHref(levels, pathname);
  const hrefs = useMemo(
    () => levels.flatMap((level) => level.groups.flatMap((group) => group.links.map((l) => l.href))),
    [levels]
  );
  useDevRouteWarmup(hrefs);

  return (
    <SettingsLayoutNav title="Settings" resizable={!mobileList}>
      {levels.map((level) => (
        <section key={level.id} className="settings-level" aria-label={level.label}>
          <h2 className="settings-level-title">{level.label}</h2>
          {level.groups.map((group, index) => (
            <div key={group.label ?? index} className="settings-level-group">
              {group.label && <h3 className="settings-level-group-title">{group.label}</h3>}
              <ul className="settings-layout-nav-list">
                {group.links.map((link) => (
                  <SettingsNavItem
                    key={link.href}
                    href={link.href}
                    label={link.label}
                    icon={link.icon}
                    active={link.href === active}
                    chevron={mobileList}
                  />
                ))}
              </ul>
            </div>
          ))}
        </section>
      ))}
    </SettingsLayoutNav>
  );
}
