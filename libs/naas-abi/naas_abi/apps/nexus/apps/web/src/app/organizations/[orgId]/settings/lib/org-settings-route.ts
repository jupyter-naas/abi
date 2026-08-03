import { orgSettingsNav } from './nav';

export interface OrgSettingsRoute {
  /** On an organization settings route at all. */
  isOrgSettingsRoute: boolean;
  /** Organization id from the URL, if any. */
  orgId: string | null;
  /** A settings section is open (general, branding, etc.). */
  isDetail: boolean;
  /** Section slug from the URL, or null for the settings index. */
  section: string | null;
  /** Human label for the active section, if any. */
  sectionLabel: string | null;
}

const navBySlug = Object.fromEntries(
  orgSettingsNav.map((item) => [item.slug, item.label])
);

const ORG_SETTINGS_SEGMENT =
  /^\/organizations\/([^/?#]+)\/settings(?:\/([^/?#]+))?(?:[/?#]|$)/;

export function parseOrgSettingsRoute(
  pathname: string | null | undefined
): OrgSettingsRoute {
  if (!pathname) {
    return {
      isOrgSettingsRoute: false,
      orgId: null,
      isDetail: false,
      section: null,
      sectionLabel: null,
    };
  }

  const match = ORG_SETTINGS_SEGMENT.exec(pathname);
  if (!match) {
    return {
      isOrgSettingsRoute: false,
      orgId: null,
      isDetail: false,
      section: null,
      sectionLabel: null,
    };
  }

  const orgId = match[1] ?? null;
  const section = match[2] ?? null;
  return {
    isOrgSettingsRoute: true,
    orgId,
    isDetail: section !== null,
    section,
    sectionLabel: section ? navBySlug[section] ?? null : null,
  };
}
