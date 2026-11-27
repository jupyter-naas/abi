'use client';

import { Suspense, useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { activeSettingsHref, type SettingsLevel } from './settings-levels';
import { SettingsLayoutNav } from './settings-layout-nav';
import { SettingsNavItem } from './settings-shell';
import { SettingsScopeSwitcher } from './settings-scope-switcher';
import { WorkspacePolicyNav, type PolicyNav } from './settings-policy-picker';
import { foldFeaturesGroup, isAccessFeaturesLink, useFeaturesSubgroup } from './features-subgroup';
import type { SettingsLink } from './settings-levels';

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
  // A workspace's column: the policy its Features and Access pages set (`?policy=`), picked under
  // the Features heading and carried by their links.
  const workspaceId = level?.id === 'workspace' ? level.index.split('/')[2] : null;
  // A workspace's Features pages hang under Access › Features, folded by default; one of them
  // open (a Configure link of Access › Features) unfolds them.
  const { groups: shownGroups, features } =
    level?.id === 'workspace' ? foldFeaturesGroup(level.groups) : { groups: level?.groups ?? [], features: null };
  const subgroupOpen = useFeaturesSubgroup((s) => s.open);
  const setSubgroupOpen = useFeaturesSubgroup((s) => s.setOpen);
  const featurePageOpen = !!features && features.links.some((link) => link.href === active);
  // The search under the pickers: a page's name and what it is for, every word.
  const [query, setQuery] = useState('');
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const searching = words.length > 0;
  const matches = (link: SettingsLink) =>
    words.every((word) => `${link.label} ${link.description ?? ''}`.toLowerCase().includes(word));
  useEffect(() => {
    if (featurePageOpen) setSubgroupOpen(true);
  }, [featurePageOpen, setSubgroupOpen]);

  const item = (link: SettingsLink, policy: PolicyNav | null, subgroup?: Parameters<typeof SettingsNavItem>[0]['subgroup']) => (
    <SettingsNavItem
      key={link.href}
      href={policy ? policy.href(link.href) : link.href}
      label={link.label}
      icon={link.icon}
      active={link.href === active}
      chevron={mobileList}
      badge={badges?.[link.href]?.text}
      badgeTitle={badges?.[link.href]?.title}
      description={link.description}
      subgroup={subgroup}
    />
  );

  const groups = (policy: PolicyNav | null) => {
    const featureLinks = features ? (policy ? policy.links(features) : features.links).filter(matches) : [];
    const drawn = shownGroups.flatMap((group, index) => {
      // While searching: the pages that match; Access › Features stays with its pages that do.
      const links = (policy ? policy.links(group) : group.links).filter(
        (link) => matches(link) || (searching && !!features && isAccessFeaturesLink(link.href) && featureLinks.length > 0)
      );
      if (searching && links.length === 0) return [];
      return [
        <div key={group.label ?? index} className="settings-level-group">
          {group.label && <h2 className="settings-level-group-title">{group.label}</h2>}
          {policy?.picker(group)}
          <ul className="settings-layout-nav-list">
            {links.map((link) =>
              features && isAccessFeaturesLink(link.href)
                ? item(link, policy, {
                    open: searching ? featureLinks.length > 0 : subgroupOpen,
                    onToggle: () => setSubgroupOpen(!subgroupOpen),
                    label: 'the Features pages',
                    children: (
                      <div data-features-subgroup="">
                        {policy?.picker(features)}
                        <ul className="settings-layout-nav-list">{featureLinks.map((sub) => item(sub, policy))}</ul>
                      </div>
                    ),
                  })
                : item(link, policy)
            )}
          </ul>
        </div>,
      ];
    });
    return drawn.length > 0 ? drawn : <p className="settings-nav-search-empty">No page matches.</p>;
  };

  return (
    <SettingsLayoutNav title={level?.label ?? 'Settings'} resizable={!mobileList}>
      {(level?.id === 'workspace' || level?.id === 'organization') && <SettingsScopeSwitcher />}
      {level && (
        <label className="settings-nav-search" data-settings-search="">
          <Search size={14} aria-hidden="true" className="settings-nav-search-icon" />
          <input
            type="search"
            aria-label="Search settings"
            placeholder="Search settings…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setQuery('');
            }}
          />
        </label>
      )}
      {workspaceId ? (
        <Suspense fallback={groups(null)}>
          <WorkspacePolicyNav workspaceId={workspaceId}>{(policy) => groups(policy)}</WorkspacePolicyNav>
        </Suspense>
      ) : (
        groups(null)
      )}
    </SettingsLayoutNav>
  );
}
