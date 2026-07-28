import { accountSettingsNav } from './nav';

export const ACCOUNT_INDEX = '/account';

export interface AccountRoute {
  /** On an account route at all. */
  isAccountRoute: boolean;
  /** A settings section is open (profile, appearance, etc.). */
  isDetail: boolean;
  /** Section slug from the URL, or null for the index. */
  section: string | null;
  /** Human label for the active section, if any. */
  sectionLabel: string | null;
}

const navBySlug = Object.fromEntries(
  accountSettingsNav.map((item) => {
    const slug = item.href.replace(`${ACCOUNT_INDEX}/`, '');
    return [slug, item.label];
  })
);

const ACCOUNT_SEGMENT = /^\/account(?:\/([^/?#]+))?(?:[/?#]|$)/;

export function parseAccountRoute(pathname: string | null | undefined): AccountRoute {
  if (!pathname) {
    return { isAccountRoute: false, isDetail: false, section: null, sectionLabel: null };
  }

  const match = ACCOUNT_SEGMENT.exec(pathname);
  if (!match) {
    return { isAccountRoute: false, isDetail: false, section: null, sectionLabel: null };
  }

  const section = match[1] ?? null;
  return {
    isAccountRoute: true,
    isDetail: section !== null,
    section,
    sectionLabel: section ? navBySlug[section] ?? null : null,
  };
}
