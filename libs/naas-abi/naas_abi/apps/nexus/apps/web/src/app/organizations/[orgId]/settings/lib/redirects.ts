/**
 * Old Organization Settings links and where they go now. No React here: src/middleware.ts
 * calls it before anything else.
 */

/**
 * Old sections and the section that replaced them: Access became Roles & permissions, then
 * Access › Policies. Roles & permissions itself is `components/access/access-paths.ts`'s
 * (`oldAccessRedirect`): each of its sections has a page of its own now. Modules is a page
 * again (Access › Modules, "<O> access"'s modules): its old links land there.
 */
const MOVED_SECTIONS = new Map<string, string>([['access', 'policies']]);

const ORG_SETTINGS_SECTION = /^\/organizations\/([^/]+)\/settings\/([^/?#]+)(?:\/.*)?$/;

/** `/organizations/<org>/settings/<moved section>[/...]` → its section now, with the query; or null. */
export function orgSettingsRedirect(pathname: string, search = ''): string | null {
  const match = ORG_SETTINGS_SECTION.exec(pathname);
  const moved = match ? MOVED_SECTIONS.get(match[2]) : undefined;
  if (!match || !moved) return null;
  const query = new URLSearchParams(search).toString();
  return `/organizations/${match[1]}/settings/${moved}${query ? `?${query}` : ''}`;
}
