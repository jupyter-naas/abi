'use client';

import { usePathname } from 'next/navigation';
import { activeSettingsHref, type SettingsLevel } from './settings-levels';
import { SettingsLayoutNav } from './settings-layout-nav';
import { SettingsNavItem } from './settings-shell';

/** A count on a link that wants attention, and what it counts. */
export type SettingsLinkBadge = { text: string; title: string };

/** The column of Settings: the pages of the level the tabs have open, the page's marked. */
export function SettingsLevelsNav({
  level,
  mobileList = false,
  badges,
}: {
  /** The level `useSettingsTabs` gives; null while it is read, or when the page's is not open. */
  level: SettingsLevel | null;
  /** The phone's list of Settings, full width. */
  mobileList?: boolean;
  /** By link: a count that wants attention (System › Jobs: its failed runs). */
  badges?: Record<string, SettingsLinkBadge>;
}) {
  const pathname = usePathname() ?? '';
  const active = level ? activeSettingsHref([level], pathname) : null;

  return (
    <SettingsLayoutNav title={level?.label ?? 'Settings'} resizable={!mobileList}>
      {level?.groups.map((group, index) => (
        <div key={group.label ?? index} className="settings-level-group">
          {group.label && <h2 className="settings-level-group-title">{group.label}</h2>}
          <ul className="settings-layout-nav-list">
            {group.links.map((link) => (
              <SettingsNavItem
                key={link.href}
                href={link.href}
                label={link.label}
                icon={link.icon}
                active={link.href === active}
                chevron={mobileList}
                badge={badges?.[link.href]?.text}
                badgeTitle={badges?.[link.href]?.title}
              />
            ))}
          </ul>
        </div>
      ))}
    </SettingsLayoutNav>
  );
}
