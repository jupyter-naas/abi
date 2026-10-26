/**
 * Old Platform Settings and System links, and where they go now. No React here:
 * src/middleware.ts calls it before anything else.
 */
import { ROLES_PATH, SYSTEM_PATH, legacySystemTabPath, systemViewPath } from '../system/system-tabs';
import {
  LEGACY_WORKSPACE_SETTINGS_SLUGS,
  PLATFORM_TABLES_PATH,
  tableFromLegacySlug,
} from './tables';

/** The first segments under /settings that Platform Settings serves. */
export const PLATFORM_SETTINGS_SECTIONS: readonly string[] = ['tables', 'system', 'roles'];

// `/workspace/<id>/admin/...`, also behind an org's `/org/<slug>` prefix.
const WORKSPACE_ADMIN = /^(?:\/org\/[^/]+)?\/workspace\/[^/]+\/admin\/(system|events)(?:\/.*)?$/;
// `/settings/<table slug>[/<row id>]`, the table pages before the Nexus tables page.
const OLD_TABLE_PAGE = /^\/settings\/([A-Za-z0-9_]+)(\/.*)?$/;

/**
 * Where an old link goes, with its query, or null when the path is not an old one:
 * - `/workspace/<id>/admin/system?tab=<tab>` → that System page (Access: Roles & permissions);
 * - `/workspace/<id>/admin/events` → System's Events page;
 * - `/settings/system/access` → Roles & permissions;
 * - `/settings/<table>[/<row id>]` → `/settings/tables/<table>[/<row id>]` (`<name>_table`
 *   was the slug of a table named like a legacy workspace settings path).
 */
export function platformSettingsRedirect(pathname: string, search = ''): string | null {
  const params = new URLSearchParams(search);
  const query = params.toString() ? `?${params.toString()}` : '';

  const admin = WORKSPACE_ADMIN.exec(pathname);
  if (admin) {
    return admin[1] === 'system' ? legacySystemTabPath(params) : `${systemViewPath('events')}${query}`;
  }

  if (pathname === `${SYSTEM_PATH}/access` || pathname.startsWith(`${SYSTEM_PATH}/access/`)) {
    return `${ROLES_PATH}${query}`;
  }

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
