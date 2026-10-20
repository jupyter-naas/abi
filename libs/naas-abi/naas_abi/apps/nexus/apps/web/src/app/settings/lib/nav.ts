import type { LucideIcon } from 'lucide-react';
import { LayoutDashboard, Table2 } from 'lucide-react';
import { PLATFORM_TABLE_LABELS, PLATFORM_TABLE_SECTIONS, platformTableSlug } from './tables';

/** Platform Settings (superadmins only), outside any organization or workspace. */
export type PlatformSettingsNavItem = {
  /** Path under /settings; '' is the dashboard at /settings. */
  slug: string;
  label: string;
  icon: LucideIcon;
};

export type PlatformSettingsNavGroup = {
  /** Shown above the items; the first group has no heading. */
  label: string | null;
  items: PlatformSettingsNavItem[];
};

export const PLATFORM_SETTINGS_INDEX = '/settings';

export const platformSettingsGroups: PlatformSettingsNavGroup[] = [
  { label: null, items: [{ slug: '', label: 'Dashboard', icon: LayoutDashboard }] },
  ...PLATFORM_TABLE_SECTIONS.map((section) => ({
    label: section.label,
    items: section.tables.map((table) => ({
      slug: platformTableSlug(table),
      label: PLATFORM_TABLE_LABELS[table],
      icon: Table2,
    })),
  })),
];

export const platformSettingsNav: PlatformSettingsNavItem[] = platformSettingsGroups.flatMap(
  (group) => group.items
);

export function platformSettingsSectionPath(slug: string): string {
  return slug ? `${PLATFORM_SETTINGS_INDEX}/${slug}` : PLATFORM_SETTINGS_INDEX;
}

export interface PlatformSettingsRoute {
  isPlatformSettingsRoute: boolean;
  /** A table or row page is open (as opposed to the dashboard). */
  isDetail: boolean;
  /** Table slug, the first path segment after /settings. */
  section: string | null;
  sectionLabel: string | null;
  /** Row id on a row page (`/settings/<table>/<row id>`), decoded. */
  rowId: string | null;
}

const navBySlug = Object.fromEntries(platformSettingsNav.map((item) => [item.slug, item.label]));

const PLATFORM_SETTINGS_PATH = /^\/settings(?:\/([^?#]*?))?\/?(?:[?#]|$)/;

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function parsePlatformSettingsRoute(
  pathname: string | null | undefined
): PlatformSettingsRoute {
  const match = pathname ? PLATFORM_SETTINGS_PATH.exec(pathname) : null;
  if (!match) {
    return {
      isPlatformSettingsRoute: false,
      isDetail: false,
      section: null,
      sectionLabel: null,
      rowId: null,
    };
  }
  const [section = null, ...rest] = (match[1] || '').split('/').filter(Boolean);
  const encodedRowId = rest.join('/');
  return {
    isPlatformSettingsRoute: true,
    isDetail: section !== null,
    section,
    sectionLabel: section ? navBySlug[section] ?? null : null,
    rowId: encodedRowId ? safeDecode(encodedRowId) : null,
  };
}
