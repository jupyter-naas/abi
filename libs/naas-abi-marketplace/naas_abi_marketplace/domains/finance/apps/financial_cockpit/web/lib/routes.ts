import type { PageId } from '@/lib/types';

/** Root path for the global theme settings page (not under an entity slug). */
export const THEME_PAGE_PATH = '/theme';

/** Pages linked from the sidebar footer instead of the main section list. */
export const SIDEBAR_FOOTER_PAGE_IDS = ['theme'] as const satisfies readonly PageId[];

export function isSidebarFooterPage(pageId: PageId): boolean {
  return (SIDEBAR_FOOTER_PAGE_IDS as readonly PageId[]).includes(pageId);
}

export function themePageHref(): string {
  return THEME_PAGE_PATH;
}

/**
 * Entity page URL. Perimeter stays in the path; filters are query params:
 *   /contract_management/treasury?scenario=2026
 *   /contract_management/treasury?scenario=2026&company=11_elzevir
 *   /contract_management/sites/foo/treasury?scenario=2026
 */
export function entityPageHref(
  entitySlug: string,
  pageId: string,
  companySlug?: string | null,
  siteSlug?: string | null,
  scenarioId?: string | null,
): string {
  const path = siteSlug
    ? `/${entitySlug}/sites/${siteSlug}/${pageId}`
    : `/${entitySlug}/${pageId}`;

  const params = new URLSearchParams();
  if (scenarioId) params.set('scenario', scenarioId);
  if (companySlug) params.set('company', companySlug);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

/** Analytics page key: path without leading slash + filter query string. */
export function analyticsPageKey(href: string): string {
  return href.replace(/^\//, '');
}
