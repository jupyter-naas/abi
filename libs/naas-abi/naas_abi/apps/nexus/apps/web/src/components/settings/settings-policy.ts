/**
 * The policy the Features and Access pages of a workspace's Settings set: "<W> access" (the
 * workspace's offer) by default, or another policy of the workspace, picked in the Settings
 * column (`SettingsPolicyPicker`) and kept in the URL (`?policy=`), which every link to those
 * pages carries. Pure: the picker and the column are `settings-policy-picker.tsx`.
 */
import { SETTINGS_GROUPS, settingsItemFor, type SettingsNavGroup } from '@/components/shell/settings-nav';

export const POLICY_PARAM = 'policy';

/** The pages of Access that edit a policy, beside every page under Features. */
const ACCESS_POLICY_PAGES = ['/settings/features', '/settings/core-services', '/settings/modules'];

/** The feature a page under Features shows, when its entry names none: Files is `files`. */
const PAGE_FEATURES: Record<string, string> = { '/settings/files': 'files' };

function featuresGroup(groups: SettingsNavGroup[]) {
  return groups.find((group) => group.label === 'Features')?.items ?? [];
}

/** Whether the page at `path` (a link, or a page under it) sets the policy picked. */
export function policyDriven(path: string, groups: SettingsNavGroup[] = SETTINGS_GROUPS): boolean {
  const item = settingsItemFor(path.replace(/[?#].*$/, ''), groups);
  if (!item) return false;
  return ACCESS_POLICY_PAGES.includes(item.href) || featuresGroup(groups).includes(item);
}

/** `href` carrying the policy picked; "<W> access" (null) is the default, left out. */
export function withPolicy(href: string, policyId: string | null): string {
  if (!policyId) return href;
  return `${href}${href.includes('?') ? '&' : '?'}${POLICY_PARAM}=${encodeURIComponent(policyId)}`;
}

/** The policy a URL's search names, or null ("<W> access"). */
export function policyOfSearch(search: Pick<URLSearchParams, 'get'> | null | undefined): string | null {
  return search?.get(POLICY_PARAM) || null;
}

/**
 * The links of the Features group under the policy picked: with another policy than "<W>
 * access" (`granted`: the features it grants), the pages of those features; a page that shows no
 * feature (Workflows: module items, set in Access › Modules) stays. With "<W> access" (null),
 * what the workspace offers: the links as they are.
 */
export function grantedLinks<T extends { href: string }>(
  links: T[],
  granted: ReadonlySet<string> | null,
  groups: SettingsNavGroup[] = SETTINGS_GROUPS
): T[] {
  if (!granted) return links;
  return links.filter((link) => {
    const item = settingsItemFor(link.href, groups);
    const feature = item ? (item.feature ?? PAGE_FEATURES[item.href]) : undefined;
    return !feature || granted.has(feature);
  });
}
