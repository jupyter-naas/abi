import { create } from 'zustand';
import type { SettingsLinkGroup } from './settings-levels';

/**
 * A workspace's Features pages (and the policy they set) sit under Access › Features in the
 * Settings column, as a sub-group folded by default; it opens when one of its pages is open (a
 * Configure link of Access › Features leads there). Pure, but for the fold state.
 */
export const FEATURES_GROUP_LABEL = 'Features';

/** The link the sub-group hangs from: Access › Features. */
export function isAccessFeaturesLink(href: string): boolean {
  return /\/settings\/features\/?$/.test(href.replace(/[?#].*$/, ''));
}

/** The groups as the column draws them: the Features group folded into Access › Features (when
 *  that link is listed), and that group apart; otherwise the groups as they are. */
export function foldFeaturesGroup(groups: SettingsLinkGroup[]): {
  groups: SettingsLinkGroup[];
  features: SettingsLinkGroup | null;
} {
  const features = groups.find((group) => group.label === FEATURES_GROUP_LABEL) ?? null;
  const anchor = groups.some((group) => group.links.some((link) => isAccessFeaturesLink(link.href)));
  if (!features || !anchor) return { groups, features: null };
  return { groups: groups.filter((group) => group !== features), features };
}

/** Whether the sub-group is unfolded: folded by default, kept while the column stays. */
export const useFeaturesSubgroup = create<{ open: boolean; setOpen: (open: boolean) => void }>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
}));
