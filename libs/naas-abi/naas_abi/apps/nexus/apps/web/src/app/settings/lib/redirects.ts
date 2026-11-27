/**
 * Old Platform Settings and System links, and where they go now. No React here:
 * src/middleware.ts calls it before anything else.
 */
import { PLATFORM_ACCESS_PATH, oldAccessRedirect, platformRolesRedirect } from '@/components/access/access-paths';
import {
  ACTIVITY_VIEWS,
  SYSTEM_PATH,
  legacyDataPath,
  legacySystemTabPath,
  systemViewPath,
} from '../system/system-tabs';
import { PLATFORM_DRIVES_PATH } from '../drives/drives-model';
import { PLATFORM_GENERAL_PATH } from '../general/general-model';
import { PLATFORM_ORGANIZATIONS_PATH } from '../organizations/organizations-model';
import { PLATFORM_THEME_PATH } from '../theme/theme-model';
import { PLATFORM_USERS_PATH } from '../users/users-model';
import { SECTION_PATHS } from './service-pages';
import {
  LEGACY_WORKSPACE_SETTINGS_SLUGS,
  PLATFORM_TABLES_PATH,
  tableFromLegacySlug,
} from './tables';

/** Modules & features, removed with the sets: what a user may use is policies' alone. */
const OLD_MODULES_PATH = '/settings/modules';

/** The Console, whose pages are the Platform tab's again. */
const OLD_CONSOLE_PATH = '/settings/console';

/** The first segments under /settings that Platform Settings serves, from its section paths. */
export const PLATFORM_SETTINGS_SECTIONS: readonly string[] = [
  PLATFORM_GENERAL_PATH,
  PLATFORM_THEME_PATH,
  PLATFORM_TABLES_PATH,
  SECTION_PATHS.system,
  SECTION_PATHS.activity,
  SECTION_PATHS.resources,
  SECTION_PATHS.data,
  PLATFORM_ORGANIZATIONS_PATH,
  PLATFORM_USERS_PATH,
  PLATFORM_ACCESS_PATH,
  PLATFORM_DRIVES_PATH,
].map((path) => path.split('/')[2]);

// `/workspace/<id>/admin/...`, also behind an org's `/org/<slug>` prefix.
const WORKSPACE_ADMIN = /^(?:\/org\/[^/]+)?\/workspace\/[^/]+\/admin\/(system|events)(?:\/.*)?$/;
// `/settings/system/<view>[/...]`: Data, Live traffic, Traces and Events were System pages.
const OLD_SYSTEM_PAGE = /^\/settings\/system\/([^/]+)\/?$/;
// `/settings/<table slug>[/<row id>]`, the table pages before the Nexus tables page.
const OLD_TABLE_PAGE = /^\/settings\/([A-Za-z0-9_]+)(\/.*)?$/;
// `/settings/users/<row id>`, a row of the users table before Users was a page of its own. A
// row's id is `user-<hex>`; an IAM user's (a person's page there now) is `usr_<…>`.
const OLD_USERS_ROW = /^\/settings\/users\/(user-[^/]+)$/;

/**
 * Where an old link goes, with its query, or null when the path is not an old one:
 * - `/settings/roles?section=…` (Roles & permissions, split up) → the page of Access it opened,
 *   People & roles to Users (`components/access/access-paths.ts`, `oldAccessRedirect`);
 * - `/workspace/<id>/admin/system?tab=<tab>` → that System page (Access: Platform › Access);
 * - `/workspace/<id>/admin/events` → System's Events page;
 * - `/settings/system/access` → Platform › Access;
 * - `/settings/system/data?service=<name>` → that service's page;
 * - `/settings/system/{traffic,traces,events}` → the same page under `/settings/activity`;
 * - `/settings/modules` (Modules & features, removed) → Platform › Access;
 * - `/settings/console` (the Console, removed) → `/settings`;
 * - `/settings/<table>[/<row id>]` → `/settings/tables/<table>[/<row id>]` (`<name>_table`
 *   was the slug of a table named like a legacy workspace settings path);
 * - `/settings/users/user-<hex>` (a users row) → `/settings/tables/users/<row id>`
 *   (`/settings/users/<IAM id>` is a person's page).
 */
export function platformSettingsRedirect(pathname: string, search = ''): string | null {
  const params = new URLSearchParams(search);
  const query = params.toString() ? `?${params.toString()}` : '';

  const roles = oldAccessRedirect(pathname, search);
  if (roles) return roles;

  const admin = WORKSPACE_ADMIN.exec(pathname);
  if (admin) {
    return admin[1] === 'system' ? legacySystemTabPath(params) : `${systemViewPath('events')}${query}`;
  }

  for (const old of [`${SYSTEM_PATH}/access`, OLD_MODULES_PATH]) {
    if (pathname === old || pathname.startsWith(`${old}/`)) return platformRolesRedirect(params);
  }
  if (pathname === OLD_CONSOLE_PATH || pathname.startsWith(`${OLD_CONSOLE_PATH}/`)) return '/settings';

  const systemPage = OLD_SYSTEM_PAGE.exec(pathname)?.[1];
  if (systemPage === 'data') return legacyDataPath(params);
  const activity = ACTIVITY_VIEWS.find((view) => view === systemPage);
  if (activity) return `${systemViewPath(activity)}${query}`;

  const usersRow = OLD_USERS_ROW.exec(pathname);
  if (usersRow) return `${PLATFORM_TABLES_PATH}/users/${usersRow[1]}${query}`;

  const table = OLD_TABLE_PAGE.exec(pathname);
  if (table) {
    const [, slug, rest = ''] = table;
    if (PLATFORM_SETTINGS_SECTIONS.includes(slug) || LEGACY_WORKSPACE_SETTINGS_SLUGS.includes(slug)) {
      return null;
    }
    return `${PLATFORM_TABLES_PATH}/${tableFromLegacySlug(slug)}${rest}${query}`;
  }
  return null;
}

/** Whether Platform Settings serves this path (it is never a legacy workspace link). */
export function isPlatformSettingsPath(pathname: string): boolean {
  if (pathname === '/settings' || pathname === '/settings/') return true;
  return PLATFORM_SETTINGS_SECTIONS.some(
    (section) => pathname === `/settings/${section}` || pathname.startsWith(`/settings/${section}/`)
  );
}
